#! /usr/bin/env python3
"""script show-spectrum.py

Reads spectrum data from Radiacode 102 device and displays and stores
the count rate history and the spectrum of deposited energies.
Data is stored in a file in human-readable yaml format.

Calculates and shows in an animated display:

 - counts:      accumulated number of counts/sec
 - count rate:  count rate
 - dose rate:   energy deposit in crystal, i.e. sum(counts*energies).
 - total dose:  total sum of deposited energies


Command line options:

  Usage: show-spectrum.py [-h] [-b BLUETOOTH_MAC] [-r] [-R] [-q]
          [-i INTERVAL] [-f FILE] [-t TIME] [-H HISTORY]

  Read and display gamma energy spectrum from RadioCode 102,
  show differential and updated cumulative spectrum,
  optionally store data to file in yaml format.

  Options:
    -h, --help          show this help message and exit
    -b BLUETOOTH_MAC, --bluetooth-mac BLUETOOTH_MAC  bluetooth MAC address of device
    -s SERIAL_NUMBER, --serial-number SERIAL_NUMBER  serial number of device
    -r, --restart       restart spectrum accumulation
    -R, --Reset         reset spectrum stored in device
    -q, --quiet         no status output to terminal
    -i INTERVAL, --interval INTERVAL update interval
    -f FILE, --file FILE  file to store results
    -t TIME, --time TIME  run time in seconds
    -H HISTORY, --history HISTORY  number of rate-history points to store in file

 Hint: use option -R to reset spectrum data in RadiaCode device

"""

import argparse
import sys
import time
import numpy as np
import yaml
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from radiacode import RadiaCode

# set backend and matplotlib style
mpl.use('Qt5Agg')
plt.style.use('dark_background')

# some constants
rho_CsJ = 4.51  # density of CsJ in g/cm^3
m_sensor = rho_CsJ * 1e-3  # Volume is 1 cm^3, mass in kg
keV2J = 1.602e-16  # conversion factor keV to Joule
depositedE2doserate = keV2J * 3600 * 1e6 / m_sensor  # dose rate in µGy/h
depositedE2dose = keV2J * 1e6 / m_sensor  # dose rate in µGy/h


class appColors:
    """Define colors used in this app"""

    title = 'goldenrod'
    text1 = 'blue'
    text2 = 'green'
    text3 = 'lightgreen'
    text4 = 'red'
    bg = 'black'
    line1 = '#F0F0C0'
    marker1 = 'orange'
    auxline = 'red'


def plot_RC102Spectrum():
    # Helper functions for conversion of channel numbers to energies
    global a0, a1, a2  # calibration constants
    # approx. calibration, overwritten by first retrieved spectrum
    a0 = 0.17
    a1 = 2.42
    a2 = 0.0004

    global mpl_active  # flag indicating that matplotlib figure exists
    mpl_active = False

    def Chan2En(C):
        # convert Channel number to Energy
        #  E = a0 + a1*C + a2 C^2
        return a0 + a1 * C + a2 * C**2

    def En2Chan(E):
        # convert Energies to Channel Numbers
        # inverse E = a0 + a1*C + a2 C^2
        c = a0 - E
        return (np.sqrt(a1**2 - 4 * a2 * c) - a1) / (2 * a2)

    def on_mpl_window_closed(ax):
        # detect when matplotlib window is closed
        global mpl_active
        print('    !!! Graphics window closed')
        mpl_active = False

    # end helpers ---------------------------------------

    # ------
    # parse command line arguments
    # ------
    parser = argparse.ArgumentParser(
        description='Read and display gamma energy spectrum from RadioCode 102, '
        + 'show differential and updated cumulative spectrum, '
        + 'optionally store data to file in yaml format.'
    )
    parser.add_argument('-b', '--bluetooth-mac', type=str, required=False, help='bluetooth MAC address of device')
    parser.add_argument('-s', '--serial-number', type=str, required=False, help='serial number of device')
    parser.add_argument('-r', '--restart', action='store_true', help='restart spectrum accumulation')
    parser.add_argument('-R', '--Reset', action='store_true', help='reset spectrum stored in device')
    parser.add_argument('-q', '--quiet', action='store_true', help='no status output to terminal')
    parser.add_argument('-i', '--interval', type=float, default=1.0, help='update interval')
    parser.add_argument('-f', '--file', type=str, default='', help='file to store results')
    parser.add_argument('-t', '--time', type=int, default=36000, help='run time in seconds')
    parser.add_argument('-H', '--history', type=int, default=500, help='number of rate-history points to store in file')
    args = parser.parse_args()

    bluetooth_mac = args.bluetooth_mac
    serial_number = args.serial_number
    restart_accumulation = args.restart
    reset_device_spectrum = args.Reset
    quiet = args.quiet
    dt_wait = args.interval
    timestamp = time.strftime('%y%m%d-%H%M', time.localtime())
    print(args.file)
    filename = args.file + '_' + timestamp + '.yaml' if args.file != '' else ''
    NHistory = args.history
    run_time = args.time
    rate_history = np.zeros(NHistory)

    if not quiet:
        print(f'\n *==* script {sys.argv[0]} executing')
        if bluetooth_mac is not None:
            print(f'    connecting via Bluetooth, MAC {bluetooth_mac}')
        elif serial_number is not None:
            print(f'    connect via USB to device with SN {serial_number}')
        else:
            print('    connect via USB')

    # ------
    # initialize and connect to RC10x device
    # ------
    rc = RadiaCode(bluetooth_mac=bluetooth_mac, serial_number=serial_number)
    serial = rc.serial_number()
    fw_version = rc.fw_version()
    status_flags = eval(rc.status().split(':')[1])[0]
    a0, a1, a2 = rc.energy_calib()
    # get initial spectrum and meta-data
    if reset_device_spectrum:
        rc.spectrum_reset()
    spectrum = rc.spectrum()
    # print(f'### Spectrum: {spectrum}')
    counts0 = np.asarray(spectrum.counts)
    NChannels = len(counts0)
    Channels = np.asarray(range(NChannels)) + 0.5
    Energies = Chan2En(Channels)
    duration_s = spectrum.duration.total_seconds()
    _t0 = time.time()
    t_start = _t0  # start time of acquisition from device

    print(f'### Found device with serial number: {serial}')
    print(f'    Firmware: {fw_version}')
    print(f'    Status flags: 0x{status_flags:x}')
    print(f'    Calibration coefficientes: a0={a0:.6f}, a1={a1:.6f}, a2={a2:.6f}')
    print(f'    Number of spectrum channels: {NChannels}')
    print(f'    Spectrum accumulation since {spectrum.duration}')

    # ------
    # initialize graphics display
    # -------
    # create a figure with two sub-plots
    fig = plt.figure('GammaSpectrum', figsize=(8.0, 8.0))
    fig.suptitle(r'Radiacode: $\gamma$-ray spectrum   ' + time.asctime(), size='large', color=appColors.title)
    fig.subplots_adjust(left=0.12, bottom=0.1, right=0.95, top=0.88, wspace=None, hspace=0.1)  #
    gs = fig.add_gridspec(nrows=15, ncols=1)
    mpl_active = True
    fig.canvas.mpl_connect('close_event', on_mpl_window_closed)

    # 1st plot for cumulative spectrum
    axE = fig.add_subplot(gs[:-6, :])
    axE.set_ylabel('Cumulative counts', size='large')
    axE.set_xlim(0.0, Energies[NChannels - 1])
    plt.locator_params(axis='x', nbins=12)
    axE.grid(linestyle='dotted', which='both')
    axE.set_yscale('log')
    axE.set_xticklabels([])
    # second x-axis for channels
    axC = axE.secondary_xaxis('top', functions=(En2Chan, Chan2En))
    axC.set_xlabel('Channel #')

    # 2nd, smaller plot for differential spectrum
    axEdiff = fig.add_subplot(gs[-6:-4, :])
    axEdiff.set_xlabel('Energy (keV)', size='large')
    axEdiff.set_ylabel('Counts', size='large')
    axEdiff.set_xlim(0.0, Energies[NChannels - 1])
    plt.locator_params(axis='x', nbins=12)
    axEdiff.grid(linestyle='dotted', which='both')

    # 3rd, small plot for rate history
    axRate = fig.add_subplot(gs[-2:, :])
    axRate.set_xlabel('History [s]', size='large')
    axRate.set_ylabel('Rate (Hz)', size='large')
    axRate.grid(linestyle='dotted', which='both')
    num_history_points = 300
    axRate.set_xlim(-num_history_points * dt_wait, 0.0)

    # create and initialize graph elements
    (line,) = axE.plot([1], [0.5], color=appColors.line1, lw=1)
    line.set_xdata(Energies)
    (line_diff,) = axEdiff.plot([1], [0.5], color=appColors.line1)
    line_diff.set_xdata(Energies)
    hrates = num_history_points * [None]
    _xplt = np.linspace(-num_history_points * dt_wait, 0.0, num_history_points)
    (line_rate,) = axRate.plot(_xplt, hrates, '.--', lw=1, markersize=4, color=appColors.line1, mec=appColors.marker1)
    line_avrate = axRate.axhline(0.0, linestyle='--', lw=1, color=appColors.auxline)

    # text for active time, cumulative and differential statistiscs
    text_active = axE.text(
        0.66,
        0.94,
        '     ',
        transform=axE.transAxes,
        color=appColors.text1,
        # backgroundcolor='white',
        alpha=0.7,
    )
    text_cum_statistics = axE.text(
        0.7,
        0.75,
        '     ',
        transform=axE.transAxes,
        color=appColors.text2,
        alpha=0.7,
    )

    # textbox and background
    rect = patches.Rectangle((0.65, 0.73), 0.34, 0.26, angle=0.0, color='white', alpha=0.7, transform=axE.transAxes)
    axE.add_patch(rect)

    text_diff_statistics = axEdiff.text(
        0.75,
        0.55,
        '     ',
        transform=axEdiff.transAxes,
        color=appColors.text3,
        alpha=0.7,
    )

    # plot in non-blocking mode
    plt.ion()  # interactive mode, non-blocking
    plt.show()

    # ---
    # initialize and start read-out loop
    # ---
    print(f'### Collecting data for {run_time:d} s')
    print('  type  <ctrl>+c to stop  ', end='\r')

    toggle = ['  \\ ', '  | ', '  / ', '  - ']
    itoggle = 0
    icount = -1
    total_time = 0
    previous_counts = counts0.copy()
    if restart_accumulation:
        counts = np.zeros(len(counts0))
        T0 = t_start
    else:
        counts = counts0.copy()
        T0 = t_start - duration_s  # start time of accumulation

    countsum0 = np.sum(counts)

    time.sleep(dt_wait - time.time() + t_start)
    try:
        while total_time < run_time and mpl_active:
            _t = time.time()  # start time of loop
            icount += 1
            # dt = _t - _t0  # last time interval
            _t0 = _t
            total_time = int(10 * (_t - T0)) / 10  # active time rounded to 0.1s
            spectrum = rc.spectrum()
            actual_counts = np.asarray(spectrum.counts)
            if not any(actual_counts):
                time.sleep(dt_wait)
                print(' accumulation time:', total_time, ' s', ' !!! waiting for data', end='\r')
                continue
            counts_diff = actual_counts - previous_counts
            previous_counts[:] = actual_counts
            counts += counts_diff
            # some statistics
            countsum = np.sum(counts)
            rate = (countsum - countsum0) / dt_wait
            rate_history[icount % NHistory] = rate
            rate_av = countsum / total_time
            hrates[icount % num_history_points] = rate
            depE = np.sum(counts_diff * Energies)  # in keV
            doserate = depE * depositedE2doserate / dt_wait
            # dose in µGy/h = µJ/(kg*h)
            deposited_energy = np.sum(counts * Energies)  # in keV
            total_dose = deposited_energy * depositedE2dose
            av_doserate = deposited_energy * depositedE2doserate / total_time

            countsum0 = countsum
            # update graphics
            line.set_ydata(counts)
            axE.relim()
            axE.autoscale_view()
            line_diff.set_ydata(counts_diff)
            axEdiff.relim()
            axEdiff.autoscale_view()
            k = icount % num_history_points
            line_rate.set_ydata(np.concatenate((hrates[k + 1 :], hrates[: k + 1])))
            axRate.relim()
            axRate.autoscale_view()
            line_avrate.set_ydata([rate_av])

            text_active.set_text('accumulation time: ' + str(total_time) + 's')
            text_cum_statistics.set_text(
                f'counts: {countsum:.5g}\n'
                + f'av. rate: {rate_av:.3g} Hz\n'
                + f'dose: {total_dose:.3g} µGy  \n'
                + f'av. doserate: {av_doserate:.3g} µGy/h'
            )
            text_diff_statistics.set_text(f'rate: {rate:.3g} Hz\n' + f'dose: {doserate:.3g} µGy/h')
            # draw data
            fig.canvas.draw_idle()
            # update status text in terminal
            if not quiet:
                print(
                    toggle[itoggle],
                    ' active:',
                    total_time,
                    's  ',
                    f'counts: {countsum:.5g}, rate: {rate:.3g} Hz, dose: {doserate:.3g} µGy/h',
                    '    (<ctrl>+c to stop)      ',
                    end='\r',
                )
            itoggle = itoggle + 1 if itoggle < 3 else 0
            # wait for corrected wait interval)
            fig.canvas.start_event_loop(max(0.9 * dt_wait, dt_wait * (icount + 2) - (time.time() - t_start)))
        # --> end while true

        print('\n' + sys.argv[0] + ': exit after ', total_time, ' s of data accumulation ...')

    except KeyboardInterrupt:
        print('\n' + sys.argv[0] + ': keyboard interrupt - ending ...')

    finally:  # store data
        if filename != '':
            print(22 * ' ' + '... storing data to yaml file ->  ', filename)
            d = dict(
                active_time=total_time,
                interval=dt_wait,
                rates=rate_history[: icount + 1].tolist()
                if icount < NHistory
                else np.concatenate((rate_history[icount + 1 :], rate_history[: icount + 1])).tolist(),
                ecal=[a0, a1, a2],
                spectrum=counts.tolist(),
            )
            with open(filename, 'w') as f:
                f.write(yaml.dump(d, default_flow_style=None))

        if mpl_active:
            input('    type <ret> to close down graphics window  --> ')

        ### get dose info from device
        #  for v in rc.data_buf():
        #    print(v.dt.isoformat(), v)


if __name__ == '__main__':
    plot_RC102Spectrum()
