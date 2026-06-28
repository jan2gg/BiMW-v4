import nidaqmx
with nidaqmx.Task() as t:
    t.ao_channels.add_ao_voltage_chan("Dev1/ao0", min_val=-10, max_val=10)
    # read back what is currently being output
    print(t.ao_channels[0].ao_dac_ref_val)