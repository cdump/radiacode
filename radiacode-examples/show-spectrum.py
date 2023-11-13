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
"""

import argparse
import sys
import time
import numpy as np
import yaml
import matplotlib as mpl
import matplotlib.pyplot as plt
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
    text1 = 'linen'
    text2 = 'lime'
    text3 = 'red'
    bg = 'black'
    line1 = '#F0F0C0'
    marker1 = 'orange'
    auxline = 'red'


def plot_RC102Spectrum():
    # Helper functions for conversion of channel numbers to energies
    global a0, a1, a2  # calibration constants
    # approx. calibration, overwritten by first  retrieved spectrum
    a0 = 0.17
    a1 = 2.42
    a2 = 0.0004

    def Chan2En(C):
        # convert Channel number to Energy
        #  E = a0 + a1*C + a2 C^2
        return a0 + a1 * C + a2 * C**2

    def En2Chan(E):
        # convert Energies to Channel Numbers
        # inverse E = a0 + a1*C + a2 C^2
        c = a0 - E
        return (np.sqrt(a1**2 - 4 * a2 * c) - a1) / (2 * a2)

    # end helpers ---------------------------------------

    # ------
    # parse command line arguments
    # ------
    parser = argparse.ArgumentParser(description='read and display spectrum from RadioCode 102')
    parser.add_argument('--bluetooth-mac', type=str, nargs='+', required=False, help='bluetooth MAC address of device')
    parser.add_argument(
        '-n',
        '--noreset',
        action='store_const',
        const=True,
        default=False,
        help='do not reset spectrum stored in device',
    )
    parser.add_argument('-i', '--interval', type=float, default=1.0, help='update interval')
    parser.add_argument('-f', '--file', type=str, default='', help='file to store results')
    parser.add_argument('-t', '--time', type=int, default=36000, help='run time in seconds')
    parser.add_argument('-H', '--history', type=int, default=500, help='number of rate history points')
    args = parser.parse_args()

    bluetooth_mac = args.bluetooth_mac
    reset_spectrum = not args.noreset
    dt_wait = args.interval
    timestamp = time.strftime('%y%m%d-%H%M', time.localtime())
    print(args.file)
    filename = args.file + '_' + timestamp + '.yaml' if args.file != '' else ''
    NHistory = args.history
    run_time = args.time
    rate_history = np.zeros(NHistory)

    print(f'\n *==* script {sys.argv[0]} executing')

    # ------
    # initialize and connect to RC10x device
    # ------
    rc = RadiaCode(bluetooth_mac=bluetooth_mac)
    serial = rc.serial_number()
    fw_version = rc.fw_version()
    status_flags = eval(rc.status().split(':')[1])[0]
    a0, a1, a2 = rc.energy_calib()
    # get initial spectrum and meta-data
    if reset_spectrum:
        rc.spectrum_reset()
    spectrum = rc.spectrum()
    # print(f'### Spectrum: {spectrum}')
    counts0 = np.asarray(spectrum.counts)
    NChannels = len(counts0)
    Channels = np.asarray(range(NChannels)) + 0.5
    Energies = Chan2En(Channels)
    duration_s = spectrum.duration.total_seconds()
    countsum0 = np.sum(np.asarray(spectrum.counts))
    _t0 = time.time()
    t_start = _t0  # start time of acquisition from device
    T0 = _t0 - duration_s  # start time of accumulation

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
    fig = plt.figure('Gamma Spectrum', figsize=(8.0, 8.0))
    fig.suptitle('Radiacode Spectrum   ' + time.asctime(), size='large', color=appColors.title)
    fig.subplots_adjust(left=0.12, bottom=0.1, right=0.95, top=0.85, wspace=None, hspace=0.1)  #
    gs = fig.add_gridspec(nrows=15, ncols=1)

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
    text_diff_statistics = axEdiff.text(
        0.75,
        0.55,
        '     ',
        transform=axEdiff.transAxes,
        color=appColors.text2,
        alpha=0.7,
    )
    # plot in non-blocking mode
    plt.ion()  # interactive mode, non-blocking
    plt.show()

    # ---
    # initialize and start read-out loop
    # ---
    print(f'### Collecting data for {run_time:d} s')
    toggle = ['  \\ ', '  | ', '  / ', '  - ']
    itoggle = 0
    icount = -1
    total_time = 0
    time.sleep(dt_wait - time.time() + t_start)
    try:
        while total_time < run_time:
            _t = time.time()  # start time of loop
            icount += 1
            # dt = _t - _t0  # last time interval
            _t0 = _t
            total_time = int(10 * (_t - T0)) / 10  # active time rounded to 0.1s
            spectrum = rc.spectrum()
            counts = np.asarray(spectrum.counts)
            if not any(counts):
                time.sleep(dt_wait)
                print(' accumulation time:', total_time, ' s', ' !!! waiting for data', end='\r')
                continue
            counts_diff = counts - counts0
            counts0[:] = counts
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

        input('    type <ret> to close down graphics window  --> ')

        ### get dose info from device
        #  for v in rc.data_buf():
        #    print(v.dt.isoformat(), v)


if __name__ == '__main__':
    plot_RC102Spectrum()
