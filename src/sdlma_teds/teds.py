from bitstring import BitStream

from .teds_element import (
    AsciiTedsElement,
    BasicTedsElement,
    Chr5TedsElement,
    ConRelResTedsElement,
    ConResTedsElement,
    ConstantTedsElement,
    DateTedsElement,
    EnumTedsElement,
    SingleTedsElement,
    UnIntTedsElement,
)


class StandardTeds:

    ni_preamble = hex(0xDA6E0CCCBA)

    @staticmethod
    def read_bitstream_from_file(file_path):
        """
        Method to read virtual teds files from the specified path.
        Because the simple read includes a lot of hex overhead only every
        fourth character is actually needed.

        :param file_path: The path to the virtual teds file.
        :return:
        """
        with open(file_path, "rb") as file:
            teds_data = file.read()
            teds_data = str(teds_data)[2:]
            return BitStream("0b" + teds_data[3::4])

    @staticmethod
    def convert_nidaqmax_list_to_bitstream(teds_data: list) -> BitStream:
        """
        Function that converts the list of integers
        received by nidaqmx to a standard teds bitstream
        :param teds_data: The teds list of integers
        :return: A standard teds bitstream
        """
        bitstream = BitStream()
        for item in teds_data:
            bits = BasicTedsElement.reverse_bitstream(BitStream(bin(item)))
            bitstream += BasicTedsElement.zero_pad_bitstream(bits)
        bitstream.pos = 0
        return bitstream

    @classmethod
    def write_teds_to_file(cls, teds: dict, filename: str):

        bitstream = BitStream(cls.ni_preamble)
        for key in teds:
            if not isinstance(teds[key], ConstantTedsElement):
                bitstream.append(teds[key].to_bits())
        with open(filename, "wb") as file:
            out = b""
            for i in range(0, len(bitstream), 1):
                out += bytes([bitstream[i]])
            file.write(out)

    def __init__(self, bitstream: BitStream, has_preamble: bool = False):
        """
        Class that extracts the data from a standard bitstream and
        turns it into a dict.
        Some vendors seem to add preambles to virtual teds files, at least
        in the case of NI. Unfortunately no documentation on this
        issue is found. The preamble seems to be consistent
        at least for NI templates.

        :param bitstream:
        :param has_preamble: Bool indicating a preamble is added to the
        bitstream that is not part of teds.
        """
        self.teds: dict = {}
        self.bitstream = bitstream
        if has_preamble:
            preamble = self.bitstream.read(40)
            if preamble != self.ni_preamble:
                raise ValueError("Preamble does not match the default")
        td: dict = {
            "manufacturer_id": UnIntTedsElement(14),
            "model_number": UnIntTedsElement(15),
            "version_letter": UnIntTedsElement(5),
            "version_number": UnIntTedsElement(6),
            "serial_number": UnIntTedsElement(24),
            "start_selector": UnIntTedsElement(2),
            "template_id": UnIntTedsElement(8),
        }
        self.process(td)

        self.check_basic_teds()

        self.load_template(self.teds["template_id"].val)

        self.end_template()

    def write_to_file(self, filename):
        self.write_teds_to_file(self.teds, filename)

    def process(self, teds_dict):
        for key in list(teds_dict):
            bits = (
                self.bitstream.read(self.bitstream.len - self.bitstream.pos)
                if (teds_dict[key].len == -1)
                else (self.bitstream.read(teds_dict[key].len))
            )
            teds_dict[key].from_bits(bits)
        self.teds.update(teds_dict)

    def load_template(self, template_id):
        match template_id:
            case 25:
                self.accelerometer_force_template()
            case 36:
                self.thermocouple_template()

    def end_template(self):
        td = {
            "calibration_date": DateTedsElement(16),
            "calibration_initals": Chr5TedsElement(15),
            "calibration_period": UnIntTedsElement(12),
            "measurement_location_id": UnIntTedsElement(11),
            "end_selector": UnIntTedsElement(2),
            "extended_end_selector": UnIntTedsElement(1),
            "user_data": AsciiTedsElement(-1),
        }
        self.process(td)

    def thermocouple_template(self):
        td = {
            "elec_sig_type": ConstantTedsElement(0, val="Voltage Sensor"),
            "minimum_temperature": ConResTedsElement(11, -273, 1),
            "maximum_temperature": ConResTedsElement(11, -273, 1),
            "minimum_electrical_output": ConResTedsElement(7, -0.025, 0.001),
            "maximum_electrical_output": ConResTedsElement(7, -0.025, 0.001),
            "mapping_method": ConstantTedsElement(0, val="Voltage Sensor"),
            "thermocouple_type": UnIntTedsElement(4),
            "cjc_required_or_compensated": UnIntTedsElement(1),
            "thermocouple_resistance": ConRelResTedsElement(12, 1, 1),
            "sensor_response_time": ConRelResTedsElement(6, 1e-6, 1),
        }
        self.process(td)

    def accelerometer_force_template(self):

        td = {
            "acceleration_force": UnIntTedsElement(1),
            "extended_functionality": UnIntTedsElement(1),
        }

        self.process(td)

        if (
            self.teds["acceleration_force"].val == 0
            and self.teds["extended_functionality"].val == 0
        ):
            self.accelerometer_no_ext_template()
        elif (
            self.teds["acceleration_force"].val == 1
            and self.teds["extended_functionality"].val == 0
        ):
            self.force_no_ext_template()
        elif (
            self.teds["acceleration_force"].val == 0
            and self.teds["extended_functionality"].val == 1
        ):
            self.accelerometer_ext_template()
        elif (
            self.teds["acceleration_force"].val == 1
            and self.teds["extended_functionality"].val == 1
        ):
            self.force_ext_template()
        else:
            raise ValueError()  # TODO: Complete exception

        td = {
            "direction": UnIntTedsElement(2),
            "transducer_weight": ConRelResTedsElement(6, 0.1, 0.1),
            "elec_sig_type": ConstantTedsElement(0, val="Voltage Sensor"),
            "map_method": ConstantTedsElement(0, val="Linear"),
            "ACDCCoupling": ConstantTedsElement(0, val="AC"),
            "sign": UnIntTedsElement(1),
            "transfer_function": UnIntTedsElement(1),
        }

        self.process(td)

        if self.teds["transfer_function"].val == 1:
            self.transfer_function_template()

        td = {
            "ref_req": ConRelResTedsElement(8, 0.35, 0.0175),
            "ref_temp": ConResTedsElement(5, 15, 0.5),
        }

        self.process(td)

    def accelerometer_no_ext_template(self):
        td = {
            "sens_ref": ConRelResTedsElement(16, 5e-7, 0.00015),
            "tf_hp_s": ConRelResTedsElement(8, 0.005, 0.03),
        }
        self.process(td)

    def force_no_ext_template(self):
        raise NotImplementedError()

    def accelerometer_ext_template(self):
        td = {
            "passive": ConstantTedsElement(0, val="0"),
            "passive_ctrl_function_mask": ConstantTedsElement(0, val="0b11"),
            "passive_read_write": ConstantTedsElement(0, val="3"),
            "passive_function_type": ConstantTedsElement(0, val="0"),
            "passive_function": ConstantTedsElement(0, val="xx,00"),
            "sens_initialize": ConstantTedsElement(0, val="0"),
            "sens_ctrl_function_mask": ConstantTedsElement(0, val="0"),
            "sens_read_write": ConstantTedsElement(0, val="3"),
            "sens_function_type": ConstantTedsElement(0, val="1"),
            "sens_function_10": ConstantTedsElement(0, val="10"),
            "sens_function_01": ConstantTedsElement(0, val="10"),
            "default_fr": UnIntTedsElement(2),
            "multiplexer_capable": UnIntTedsElement(1),
            "sens_ref_01": ConRelResTedsElement(16, 5e-7, 1),
            "sens_ref_10": ConRelResTedsElement(16, 5e-7, 1),
            "tf_hp_s_01": ConRelResTedsElement(8, 0.005, 1),
            "tf_hp_s_10": ConRelResTedsElement(8, 0.005, 1),
        }
        self.process(td)

    def force_ext_template(self):
        raise NotImplementedError()

    def transfer_function_template(self):
        td = {
            "tf_sp": ConRelResTedsElement(7, 10, 0.05),
            "tf_kpr": ConRelResTedsElement(9, 100, 0.01),
            "tf_kpq": ConRelResTedsElement(9, 0.4, 0.01),
            "tf_sl": ConResTedsElement(7, -6.3, 0.1),
            "temp_coef": ConResTedsElement(6, -0.8, 0.025),
        }
        self.process(td)

    def check_basic_teds(self):
        if self.teds["version_number"] != 2:
            print("Sensor utilizes legacy teds format!")

    def print_teds_array(self):
        for name, item in self.teds.items():
            print(f"Name: {name}")
            print(f"Value: {item.val}")
            print("------------------------------------------------")
