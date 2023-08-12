#! /usr/bin/env python3
"""script readRC102

  Read spectrum data from Radiacode 102 device and displays the rate 
  and cumulated conts of deposited energies as a histogram

  Calculates and displays:

   - counts:  accumulated number of counts/sec
   - rate:    actual count rate
   - dose:    energy deposit in crystal, sum(counts*energies).
"""

import sys, argparse
import time, datetime
import numpy as np, matplotlib as mpl, matplotlib.pyplot as plt

from radiacode import RadiaCode

# some constants
rho_CsJ = 4.51  # density of CsJ in g/cm^3
m_sensor = rho_CsJ * 1e-3  # Volume is 1 cm^3, mass in kg
keV2J = 1.602e-16
depositedE2dose = keV2J * 3600 * 1e6 / m_sensor  # dose rate in µGy/h


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
    parser = argparse.ArgumentParser(description="read and display spectrum from RadioCode 102")
    parser.add_argument(
        '--bluetooth-mac', type=str, nargs='+', required=False, help='bluetooth MAC address of radiascan device'
    )
    parser.add_argument(
        '-n',
        '--noreset',
        action='store_const',
        const=True,
        default=False,
        help='do not reset spectrum stored in device',
    )
    parser.add_argument('-i', '--interval', type=float, default=1.0, help='update interval')
    args = parser.parse_args()

    bluetooth_mac = args.bluetooth_mac
    reset_spectrum = True if args.noreset == False else False
    interval = args.interval

    # ------
    # connect to device
    # ------
    print(f' *==* script {sys.argv[0]} executing')
    print('--------  Device Info')
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
    T0 = time.time() - duration_s
    t0 = T0

    print(f'### Serial number: {serial}')
    print(f'    Firmware: {fw_version}')
    print(f'    Status flags: 0x{status_flags:x}')
    print(f'    Calibration coefficientes: a0={a0:.6f}, a1={a1:.6f}, a2={a2:.6f}')
    print(f'    Number of spectrum channels: {NChannels}')
    print(f'    Spectrum accumulation since {spectrum.duration}')

    # ------
    # # plot data
    # -------
    # figure with two sub-plot
    fig = plt.figure("Gamma Spectrum", figsize=(8.0, 6.0))
    fig.suptitle('Radiacode Spectrum   ' + time.asctime(), size='large', color='b')
    fig.subplots_adjust(left=0.12, bottom=0.1, right=0.95, top=0.85, wspace=None, hspace=0.25)  #
    gs = fig.add_gridspec(nrows=4, ncols=1)
    # define subplots
    axE = fig.add_subplot(gs[:-1, :])
    ### axE.set_xlabel('Energy (keV)', size='large')
    axE.set_ylabel('Cumulative counts', size='large')
    axE.set_xlim(0.0, Energies[NChannels - 1])
    plt.locator_params(axis='x', nbins=12)
    axE.grid(linestyle='dotted', which='both')
    axE.set_yscale('log')
    # second x-axis for channels
    axC = axE.secondary_xaxis('top', functions=(En2Chan, Chan2En))
    axC.set_xlabel('Channel #')
    # smaller ploit for differential spectrum
    axEdiff = fig.add_subplot(gs[-1, :])
    axEdiff.set_xlabel('Energy (keV)', size='large')
    axEdiff.set_ylabel('Rate (Hz)', size='large')
    axEdiff.set_xlim(0.0, Energies[NChannels - 1])
    plt.locator_params(axis='x', nbins=12)
    axEdiff.grid(linestyle='dotted', which='both')

    # plot initial data
    (line,) = axE.plot([1], [0.5])
    line.set_xdata(Energies)
    (line_diff,) = axEdiff.plot([1], [0.5])
    line_diff.set_xdata(Energies)

    # text for active time and statistiscs
    text_active = axE.text(
        0.8,
        0.94,
        '     ',
        transform=axE.transAxes,
        color='darkred',
        # backgroundcolor='white',
        alpha=0.7,
    )
    text_statistics = axE.text(
        0.75,
        0.8,
        '     ',
        transform=axE.transAxes,
        color='darkblue',
        # backgroundcolor='white',
        alpha=0.7,
    )
    # plot in non-blocking mode
    plt.ion()  # interactive mode, non-blocking
    plt.show()

    # start read-out loop
    toggle = ['  \ ', '  | ', '  / ', '  - ']
    itoggle = 0
    print()
    time.sleep(interval)
    while True:
        t = time.time()
        dt = t - t0  # last time interval
        t0 = t
        dT = int(10 * (t - T0)) / 10  # active time in units of 1/10 s
        spectrum = rc.spectrum()
        counts = np.asarray(spectrum.counts)
        if not any(counts):
            time.sleep(interval)
            print('       active:', dT, 's', ' !!! waiting for data', end='\r')
            continue
        counts_diff = (counts - counts0) / dt
        counts0[:] = counts
        # some statistics
        countsum = np.sum(counts)
        rate = (countsum - countsum0) / dt
        # dose in µGy/h = µJ/(kg*h)
        deposited_energy = np.sum(counts * Energies)  # in keV
        dose = deposited_energy * depositedE2dose / dT
        countsum0 = countsum
        # update graphics
        line.set_ydata(counts)
        axE.relim()
        axE.autoscale_view()
        line_diff.set_ydata(counts_diff)
        axEdiff.relim()
        axEdiff.autoscale_view()

        text_active.set_text('active: ' + str(dT) + 's')
        text_statistics.set_text(f'counts: {countsum:.5g} \n' + f'rate: {rate:.3g} Hz\n' + f'dose: {dose:.3g} µGy/h')
        fig.canvas.draw_idle()
        fig.canvas.start_event_loop(interval)
        print(
            toggle[itoggle],
            ' active:',
            dT,
            's  ',
            f'counts: {countsum:.5g}, rate: {rate:.3g} Hz, dose: {dose:.3g} µGy/h',
            15 * ' ',
            end='\r',
        )
        itoggle = itoggle + 1 if itoggle < 3 else 0

    ### dose info from device
    #  for v in rc.data_buf():
    #    print(v.dt.isoformat(), v)


if __name__ == '__main__':
    plot_RC102Spectrum()
