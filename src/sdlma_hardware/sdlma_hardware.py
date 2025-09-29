import json
import os
from abc import ABC, abstractmethod

import nidaqmx
import scipy
from nidaqmx.constants import (
    AccelSensitivityUnits,
    AccelUnits,
    AcquisitionType,
    ForceIEPESensorSensitivityUnits,
    ForceUnits,
)
from nidaqmx.system import System

from sdlma_teds.teds import StandardTeds


class SDLMAChannel:

    def __init__(self, name: str, hw_teds: bool, voltage_range: tuple):
        """
        Custom Channel implementation for sdlma.

        :param name: Unique name that maps to device and channel. e.g.
        Dev1/channel 2
        :param hw_teds: Bool indicating that channel is hardware teds capable
        :param voltage_range: The operating range of the channel -> depends
        on the device
        """
        self.name = name
        self.hw_teds = hw_teds
        self.channel_info = {}
        self.is_resp = False
        self.direction = "+Z"
        self.voltage_range = voltage_range
        self.disp_name = ""

    def set_channel_info(
        self,
        teds_list: list = None,
        teds_file_path: str = None,
        teds_info: dict = None,
    ) -> None:
        """
        Method to set the channel info. Depending on  hw teds, vir. teds or
        no teds.
        :param teds_list: Teds list of nidaqmx format.
        :param teds_file_path: Teds file for virtual teds
        :param teds_info: Dict for no teds
        """
        if teds_list:
            bitstream = StandardTeds.convert_nidaqmax_list_to_bitstream(
                teds_list
            )
            self.channel_info = StandardTeds(bitstream).teds
            self.is_resp = self.channel_info["acceleration_force"].val == 0
        elif teds_file_path:
            bitstream = StandardTeds.read_bitstream_from_file(teds_file_path)
            self.channel_info = StandardTeds(bitstream, has_preamble=True).teds
            self.is_resp = self.channel_info["acceleration_force"].val == 0
        elif teds_info:
            self.channel_info = teds_info
            self.channel_info["min_val"] = (
                self.voltage_range[0] / self.channel_info["sens_ref"]
            )
            self.channel_info["max_val"] = (
                self.voltage_range[1] / self.channel_info["sens_ref"]
            )
            print(self.channel_info["sens_ref"])
        else:
            raise ValueError("No hw_teds, vi_teds or sensor info given")


class SDLMATask(ABC):

    @classmethod
    def from_file(cls, file_path: str, *args, **kwargs):
        with open(file_path, "r") as f:
            data = json.loads(f.read())
            return cls(*args, **data, **kwargs)

    @classmethod
    def delete_file(cls, file_path: str):
        if os.path.exists(file_path):
            os.remove(file_path)

    def __init__(
        self,
        name: str,
        meas_time: float,
        sampling_freq: int,
        channels: list[SDLMAChannel],
    ):
        """
        Task prototype class. Not Vendor specific.
        :param name: The name of the meas task
        :param meas_time: The measurement time
        :param sampling_freq: The sampling frequency
        :param channels: The channels that shall be used
        """
        self.name = name
        self.meas_time = meas_time
        self.sampling_freq = sampling_freq
        self.channels = channels
        self.num_samples = int(self.meas_time * self.sampling_freq)

        self.task = None

    @abstractmethod
    def start(self):
        """Method to start the task"""
        pass

    @abstractmethod
    def read(self, number_of_samples: int):
        """Method to read n samples"""
        pass

    @abstractmethod
    def stop(self):
        """Method to stop the task"""
        pass


# https://stackoverflow.com/questions/43851294/pythonic-way-to-find-the-nearest-lower-integer-for-x-that-is-evenly-divisible-by
def nearest_even_divisor(n: int, target: int) -> int:
    """
    Helper function to calculate the nearest even divisors.
    Utilized for example in n sample callback.
    :param n: The total number of samples
    :param target: the ideal target
    :return: The closest even divisor
    """
    divisors = [i for i in range(1, n + 1) if n % i == 0]
    closest = min(divisors, key=lambda x: abs(x - target))
    return closest


class SDLMANiTask(SDLMATask):

    def __init__(
        self,
        name: str,
        meas_time: float,
        sampling_freq: int,
        channels: list[SDLMAChannel],
        n_sample_callback: callable,
        done_callback: callable,
    ):
        """
        Custom task implementation for ni daqs.
        :param name: The name of the meas task
        :param meas_time: The measurement time
        :param sampling_freq: The sampling frequency
        :param channels: The channels that shall be used

        :param n_sample_callback: Callback function after n samples.
        :param done_callback: Callback function when done.
        """
        super().__init__(name, meas_time, sampling_freq, channels)
        self.task = nidaqmx.Task(name)
        self.add_channels()
        buffer = int((sampling_freq * meas_time))
        self.callback_interval = nearest_even_divisor(buffer, 2000)
        self.init_task(n_sample_callback, done_callback)

    def init_task(self, n_sample_callback, done_callback):
        """
        Method to initialize the timing and callback
        functions.

        :param n_sample_callback: Callback function after n samples.
        :param done_callback: Callback function when done.
        :return:
        """
        self.task.timing.cfg_samp_clk_timing(
            rate=self.sampling_freq,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=self.num_samples,
        )
        assert self.sampling_freq == self.task.timing.samp_clk_rate
        self.task.register_every_n_samples_acquired_into_buffer_event(
            self.callback_interval, n_sample_callback
        )
        self.task.register_done_event(done_callback)

    def add_channels(self):
        """
        Function that adds the selected channels to the task
        according to their specifications.
        """
        for gui_channel in self.channels:
            channel = gui_channel.channel
            if channel.hw_teds:
                if channel.is_resp:
                    self.task.ai_channels.add_teds_ai_accel_chan(
                        channel.name,
                        units=AccelUnits.METERS_PER_SECOND_SQUARED,
                    )
                else:
                    self.task.ai_channels.add_teds_ai_force_iepe_chan(
                        channel.name, units=ForceUnits.NEWTONS
                    )
            else:

                if channel.is_resp:
                    self.task.ai_channels.add_ai_accel_chan(
                        channel.name,
                        units=AccelUnits.METERS_PER_SECOND_SQUARED,
                        sensitivity=channel.channel_info["sens_ref"]
                        * scipy.constants.g,
                        sensitivity_units=AccelSensitivityUnits.MILLIVOLTS_PER_G,
                        min_val=channel.channel_info["min_val"],
                        max_val=channel.channel_info["max_val"],
                    )
                else:
                    self.task.ai_channels.add_ai_force_iepe_chan(
                        channel.name,
                        units=ForceUnits.NEWTONS,
                        sensitivity=channel.channel_info["sens_ref"],
                        sensitivity_units=ForceIEPESensorSensitivityUnits.MILLIVOLTS_PER_NEWTON,
                        min_val=channel.channel_info["min_val"],
                        max_val=channel.channel_info["max_val"],
                    )

    def start(self):
        self.task.start()

    def stop(self):
        self.task.stop()

    def read(self, number_of_samples):
        return self.task.read(number_of_samples_per_channel=number_of_samples)

    def close(self):
        """
        Method to delete the task for ni devices.
        """
        self.task.close()

    def __del__(self):
        self.close()


class SDLMAHardware:

    def __init__(self):
        """
        Helper class to scan for available hardware.
        Currently only supports ni devices
        """
        self.sdlma_channels = []

    def get_available_ni_channels(self):
        """
        Method to check if any devices are available,
        read all channels and check for teds.
        Adds all available channels to list of channels.
        """
        system = System().local()
        for device in system.devices:
            voltage_range = device.ai_voltage_rngs
            for channel in device.ai_physical_chans:
                hw_teds, bitstream = self.check_ni_teds(channel)
                channel = SDLMAChannel(channel.name, hw_teds, voltage_range)
                if hw_teds:
                    channel.set_channel_info(teds_list=bitstream)
                self.sdlma_channels.append(channel)

    @staticmethod
    def check_ni_teds(
        channel: nidaqmx.system.physical_channel,
    ) -> tuple[bool, list]:
        """
        Function to check for hw teds information
        :param channel: The channel that should be checked.
        :return: bool indicating if hw teds and bitstream
        """
        try:
            if channel.teds_bit_stream:
                return True, channel.teds_bit_stream
        except nidaqmx.errors.DaqError as exc:
            if exc.error_code == -200709:  # TEDS not found
                return False, []
            else:
                raise exc  # Unknown Error - Reraise
