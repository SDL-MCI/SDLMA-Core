"""
SDLMA Measurement Module
"""

import copy
import os.path
from dataclasses import asdict, dataclass

import h5py
import numpy as np
from sdypy import FRF


# https://pyfrf.readthedocs.io/en/latest/Showcase.html#SEP-005-input-data-compatibility-(MIMO-showcase)
@dataclass
class SDLMATimeSeriesSEP005:
    data: np.ndarray
    unit_str: str
    fs: int
    quantity: str
    name: str
    direction: str

    @staticmethod
    def from_array(
        arr: np.ndarray,
        unit_str: str,
        fs: int,
        quantity: str,
        names: list[str],
        directions: list[str],
    ) -> list[dict]:
        time_series_list = []
        for i in range(arr.shape[0]):
            time_series = SDLMATimeSeriesSEP005(
                arr[i, :],
                unit_str,
                fs,
                quantity,
                names[i],
                directions[i],
            )
            time_series_list.append(asdict(time_series))
        return time_series_list


class SDLMAMeasurement:

    def __init__(
        self,
        name: str,
        window_len: int,
        sampling_freq: int,
        exc: list[dict],
        resp: list[dict],
        comment: str,
    ):
        """
        Class that represents a measurement in sdlma.

        :param window_len: The window length utilized in frf calculation (
        also called fft_len by sdypy)
        :param sampling_freq: The frequency that was utilized to sample the
        meas data
        :param exc: The list of exc signals
        :param resp: The list of resp signals
        :param comment: An optional comment
        """
        self._name = name
        self._window_len = int(window_len)
        self._sampling_freq = int(sampling_freq)
        self._exc = exc
        self._resp = resp
        self._comment = comment
        self.frf_object = self.calc_frf(self.exc, self.resp, self.window_len)

    @property
    def name(self) -> str:
        """Name used to describe the dataset"""
        return self._name

    @property
    def window_len(self) -> int:
        """Window length used in the analysis."""
        return self._window_len

    @property
    def sampling_freq(self) -> int:
        """Sampling frequency used in the measurement."""
        return self._sampling_freq

    @property
    def exc(self) -> list[dict]:
        """The excitation signal"""
        return self._exc

    @property
    def resp(self) -> list[dict]:
        """The response signal"""
        return self._resp

    @property
    def comment(self) -> str:
        """The comment for the measurement"""
        return self._comment

    @staticmethod
    def calc_frf(exc: list, resp: list, window_len: int) -> FRF.FRF:
        """
        Function to calculate the frf from
        a given excitation and response signal list

        :param exc: A list of excitation signals
        :param resp: A list of response signals
        :param window_len: The window length
        :return: A pyfrf.FRF Object with applied H1 filter
        """
        with np.errstate(divide="ignore", invalid="ignore"):
            frf_object = FRF.FRF(
                sampling_freq=None,
                exc=SDLMAMeasurement.prepare_time_series(exc, window_len),
                resp=SDLMAMeasurement.prepare_time_series(resp, window_len),
                fft_len=window_len,
                frf_type="H1",
            )
            return frf_object

    @staticmethod
    def prepare_time_series(meas_list: list, window_len: int) -> list:
        """
        Function that turns a measurement in the meas list
        :param meas_list: The list containing the impact measurements
        :param window_len: The number of samples for each impact
        :return: A sep_005 compliant time series
        """
        out = None
        for item in meas_list:
            if not out:
                # needed otherwise the original dict will be edited
                out = copy.deepcopy(item)
                out["data"] = out["data"].reshape(1, -1)
            else:
                out["name"] += "_" + item["name"]
                out["data"] = np.vstack([out["data"], item["data"]])

        num_impacts = out["data"].shape[1] / window_len
        assert num_impacts % 1 == 0
        chunks = np.split(out["data"], int(num_impacts), axis=1)
        out_list = []
        for i in range(len(chunks)):
            data = {
                "data": chunks[i],
                "unit_str": out["unit_str"],
                "fs": out["fs"],
                "quantity": out["quantity"],
                "name": out["name"],
                "direction": out["direction"],
            }
            out_list.append(data)
        return out_list

    def get_names(self) -> tuple[list[str], list[str]]:
        """
        Method to get the names of the excitation and response signals
        :return: A tuple containing the names
        """
        exc_names = [item["name"] for item in self.exc]
        resp_names = [item["name"] for item in self.resp]
        return exc_names, resp_names

    @staticmethod
    def import_from_hd5f_file(filename: str):
        """
        Function to create a SDLMAMeasurement Object from an h5 datastore
        :param filename: The full path to the file!
        """
        # TODO: check if legal h5file
        with h5py.File(filename, "r") as h5_file:
            name = h5_file.attrs["name"]
            window_len = h5_file.attrs["window_len"]
            sampling_freq = h5_file.attrs["sampling_freq"]
            comment = h5_file.attrs["comment"]
            exc = []
            resp = []
            for category, container in [("exc", exc), ("resp", resp)]:
                grp = h5_file[category]
                for key in grp:
                    sig_grp = grp[key]
                    data = sig_grp["data"][()]
                    unit_str = sig_grp.attrs["unit_str"]
                    fs = int(sig_grp.attrs["fs"])
                    quantity = sig_grp.attrs["quantity"]
                    sig_name = sig_grp.attrs["name"]
                    sig_direction = sig_grp.attrs["direction"]
                    time_series = SDLMATimeSeriesSEP005(
                        data=data,
                        unit_str=unit_str,
                        fs=fs,
                        quantity=quantity,
                        name=sig_name,
                        direction=sig_direction,
                    )
                    container.append(asdict(time_series))
        return SDLMAMeasurement(
            name=name,
            window_len=window_len,
            sampling_freq=sampling_freq,
            exc=exc,
            resp=resp,
            comment=comment,
        )

    def check_double_impact(
        self,
        overflow_samples: int,
        double_impact_limit: float,
    ) -> list[int]:
        """
        Method that checks each impact for a double impact
        according to the given limits.

        :param overflow_samples: The number of samples that need to be
        equal to max for overflow identification
        :param double_impact_limit:  Represents the ratio of freqency
        content of the double vs single hit
        :return: A list of integers, if the index is present a double impact
        was found
        """
        num_impacts = self.exc[0]["data"].shape[0] / self.window_len
        assert num_impacts % 1 == 0  # Integer check
        num_impacts = int(num_impacts)
        exc_list = SDLMAMeasurement.prepare_time_series(
            self.exc, self.window_len
        )
        resp_list = SDLMAMeasurement.prepare_time_series(
            self.resp, self.window_len
        )
        ret = []
        for i in range(num_impacts):
            frf = FRF.FRF(
                sampling_freq=self.sampling_freq, fft_len=self.window_len
            )
            if not frf.is_data_ok(
                exc_list[i]["data"],
                resp_list[i]["data"],
                overflow_samples,
                double_impact_limit,
            ):
                ret.append(i)
        return ret

    def export_to_hd5f_file(self, filename: str):
        """
        Method to export the object to a h5 datastore
        :param filename: The full path to the file!
        """
        if os.path.splitext(filename)[1] != ".h5":
            filename += ".h5"
        with h5py.File(filename, "w") as h5_file:
            h5_file.attrs["name"] = self.name
            h5_file.attrs["window_len"] = self.window_len
            h5_file.attrs["sampling_freq"] = self.sampling_freq
            h5_file.attrs["comment"] = self.comment
            for category, measurements in [
                ("exc", self._exc),
                ("resp", self._resp),
            ]:
                grp = h5_file.create_group(category)
                for i, measurement in enumerate(measurements):
                    sig_grp = grp.create_group(f"signal_{i}")
                    sig_grp.create_dataset("data", data=measurement["data"])
                    sig_grp.attrs["unit_str"] = measurement["unit_str"]
                    sig_grp.attrs["fs"] = measurement["fs"]
                    sig_grp.attrs["quantity"] = measurement["quantity"]
                    sig_grp.attrs["name"] = measurement["name"]
                    sig_grp.attrs["direction"] = measurement["direction"]
