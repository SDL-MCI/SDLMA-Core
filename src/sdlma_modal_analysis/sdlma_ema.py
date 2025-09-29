from dataclasses import asdict

import h5py
import numpy as np
from sdypy import EMA, FRF

from sdlma_modal_analysis.sdlma_measurement import (
    SDLMAMeasurement,
    SDLMATimeSeriesSEP005,
)


class SDLMAEMA:

    def __init__(
        self,
        lower: float,
        upper: float,
        pol_order: int,
        solver: str,
        freq_estimates: list[int],
        measurements: list[SDLMAMeasurement] = None,
        nat_freq: list[float] = None,
        nat_xi: list[float] = None,
        H: np.ndarray = None,
        A: np.ndarray = None,
        phi: np.ndarray = None,
    ):
        """
        Wrapper for sdypy ema to perform expiremental modal analysys

        :param lower: lower frequency boundary
        :param upper: upper frequency boundary
        :param pol_order: polynomial order for curve fit
        :param solver: Solver utilized in sdypy ema
        :param freq_estimates: List of natural frequency estimates
        :param measurements: Measurement objects used in ema
        :param nat_freq: List of natural frequencies
        :param nat_xi: List of damping
        :param H: Reconstructed frf
        :param A: Reconstructed modal characteristics
        :param phi: Reconstructed modal shapes
        """
        self.lower = lower
        self.upper = upper
        self.pol_order = pol_order
        self.solver = solver
        self.freq_estimates = freq_estimates

        self.frf_matrix = None
        self.f_axis = None
        self.coherence = None
        self.ema_object = None
        self.measurements = [] if measurements is None else measurements

        self.nat_freq = nat_freq  # natural frequencies
        self.nat_xi = nat_xi  # damping coefficients
        self.H = H  # reconst. FRF Matrix
        self.A = A  # modal constants
        self.phi = phi  # modal constants

    def add_measurement(self, sdlma_measurement: SDLMAMeasurement):
        """
        Method to add a measurement to the lists of measurements

        :param sdlma_measurement: SDLMAMeasurement object
        """
        self.measurements.append(sdlma_measurement)

    def get_unique_names(self) -> list[str]:
        """
        Method to get all unique signal names
        :return: List of unique signal names
        """
        unique_names = []
        for measurement in self.measurements:
            exc_names, resp_names = measurement.get_names()
            for name in exc_names + resp_names:
                if name not in unique_names:
                    unique_names.append(name)
        return unique_names

    def remove_measurement(self, sdlma_measurement: SDLMAMeasurement):
        """
        Method to remove a measurement from the lists of measurements
        :param sdlma_measurement: SDLMAMeasurement object
        """
        pass

    def calc(self):
        """
        Method that performs the curve fitting and modal parameter
        reconstruction via sdypy ema
        """
        frf_matrix = None
        f_axis = None
        coherence = None
        driving_point = 0
        for i, measurement in enumerate(self.measurements):
            for resp in measurement.resp:
                if measurement.exc[0]["name"] == resp["name"]:
                    driving_point = i
            frf_data = measurement.frf_object.get_FRF("H1", form="accelerance")
            assert frf_data.shape[1] == 1
            frf_data = frf_data[:, 0, 1:]  # ONLY SIMO
            coherence_data = measurement.frf_object.get_coherence()[:, 1:]

            if not isinstance(frf_matrix, np.ndarray):
                frf_matrix = frf_data
                coherence = coherence_data
                f_axis = measurement.frf_object.get_f_axis()[1:]
            else:
                frf_matrix = np.concatenate([frf_matrix, frf_data], axis=0)
                coherence = np.concatenate([coherence, coherence_data], axis=0)
        # assert driving_point is not None
        self.frf_matrix = frf_matrix
        self.f_axis = f_axis
        self.coherence = coherence
        self.ema_object = EMA.Model(
            frf=frf_matrix,  # resp DOF, all data
            freq=f_axis,
            lower=self.lower,
            upper=self.upper,
            pol_order_high=self.pol_order,
            frf_type="accelerance",
            driving_point=driving_point,
        )

    def select_poles(self):
        """
        Method to select poles using sdypy ema
        """
        if self.freq_estimates:
            self.ema_object.select_closest_poles(
                self.freq_estimates, f_window=1
            )
        else:
            self.ema_object.select_poles()
        self.nat_freq = self.ema_object.nat_freq
        self.nat_xi = self.ema_object.nat_xi
        self.H, self.A = self.ema_object.get_constants()
        self.phi = self.ema_object.phi

    def get_poles(self):
        """
        Method to get poles using sdypy ema
        """
        self.ema_object.get_poles(method=self.solver)

    @staticmethod
    def import_from_hd5f_file(filename: str):
        """
        Function to create a SDLMAEMA Object from an h5 datastore
        :param filename: The full path to the file!
        """
        with h5py.File(filename, "r") as h5_file:
            lower = float(h5_file.attrs["lower"])
            upper = float(h5_file.attrs["upper"])
            pol_order = int(h5_file.attrs["pol_order"])
            solver = h5_file.attrs["solver"]
            nat_freq = h5_file["nat_freq"][()]
            nat_xi = h5_file["nat_xi"][()]
            A = h5_file["A"][()]
            H = h5_file["H"][()]
            phi = h5_file["phi"][()]
            freq_estimates = h5_file["freq_estimates"][()]
            measurements = []
            datagrp = h5_file["measurements"]
            for measurement in datagrp:
                meas_grp = datagrp[measurement]
                name = meas_grp.attrs["name"]
                window_len = meas_grp.attrs["window_len"]
                sampling_freq = meas_grp.attrs["sampling_freq"]
                comment = meas_grp.attrs["comment"]
                exc = []
                resp = []
                for category, container in [("exc", exc), ("resp", resp)]:
                    sig_grp = meas_grp[category]
                    for key in sig_grp:
                        signal = sig_grp[key]
                        data = signal["data"][()]
                        unit_str = signal.attrs["unit_str"]
                        fs = int(signal.attrs["fs"])
                        quantity = signal.attrs["quantity"]
                        sig_name = signal.attrs["name"]
                        direction = (
                            "+Z"
                            if ("direction" not in signal.attrs)
                            else signal.attrs["direction"]
                        )
                        time_series = SDLMATimeSeriesSEP005(
                            data=data,
                            unit_str=unit_str,
                            fs=fs,
                            quantity=quantity,
                            name=sig_name,
                            direction=direction,
                        )
                        container.append(asdict(time_series))
                measurements.append(
                    SDLMAMeasurement(
                        name, window_len, sampling_freq, exc, resp, comment
                    )
                )
        sdlma_ema = SDLMAEMA(
            lower=lower,
            upper=upper,
            pol_order=pol_order,
            solver=solver,
            freq_estimates=freq_estimates,
            measurements=measurements,
            nat_freq=nat_freq,
            nat_xi=nat_xi,
            A=A,
            H=H,
            phi=phi,
        )
        return sdlma_ema

    def export_to_hd5f_file(self, filename: str):
        """
        Method to export the object to a h5 datastore
        :param filename: The full path to the file!
        """
        with h5py.File(filename, "w") as h5_file:
            h5_file.attrs["lower"] = self.lower
            h5_file.attrs["upper"] = self.upper
            h5_file.attrs["pol_order"] = self.pol_order
            h5_file.attrs["solver"] = self.solver
            h5_file.create_dataset("nat_freq", data=self.nat_freq)
            h5_file.create_dataset("nat_xi", data=self.nat_xi)
            h5_file.create_dataset("A", data=self.A)
            h5_file.create_dataset("H", data=self.H)
            h5_file.create_dataset("phi", data=self.phi)
            h5_file.create_dataset("freq_estimates", data=self.freq_estimates)
            datagrp = h5_file.create_group("measurements")
            for i, measurement in enumerate(self.measurements):
                meas_grp = datagrp.create_group(f"measurement_{i}")
                meas_grp.attrs["name"] = measurement.name
                meas_grp.attrs["window_len"] = measurement.window_len
                meas_grp.attrs["sampling_freq"] = measurement.sampling_freq
                meas_grp.attrs["comment"] = measurement.comment
                for category, signals in [
                    ("exc", measurement._exc),
                    ("resp", measurement._resp),
                ]:
                    sig_grp = meas_grp.create_group(category)
                    for i, signal in enumerate(signals):
                        grp = sig_grp.create_group(f"signal_{i}")
                        grp.create_dataset("data", data=signal["data"])
                        grp.attrs["unit_str"] = signal["unit_str"]
                        grp.attrs["fs"] = signal["fs"]
                        grp.attrs["quantity"] = signal["quantity"]
                        grp.attrs["name"] = signal["name"]
                        grp.attrs["direction"] = signal["direction"]
