import enum
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from bitstring import Bits


@dataclass
class BasicTedsElement(ABC):
    len: int

    def __init__(self):
        self.val = None

    @abstractmethod
    def from_bits(self, bitstream):
        pass

    @abstractmethod
    def to_bits(self):
        if self.val is None:
            raise ValueError("Cannot convert None to bits")

    @staticmethod
    def zero_pad_bitstream(bitstream):
        target_len = math.ceil(len(bitstream) / 8) * 8
        pad = target_len - len(bitstream)
        zeros = f"{'0' * pad}"
        test = bitstream + Bits(bin=zeros)
        return test

    @staticmethod
    def reverse_bitstream(bitstream):
        return bitstream[::-1]

    def to_bitstream(self, int_val):
        return self.reverse_bitstream(Bits(uint=int_val, length=self.len))


@dataclass
class UnIntTedsElement(BasicTedsElement):
    val: Any = None

    def from_bits(self, bitstream):
        bitstream = self.reverse_bitstream(self.zero_pad_bitstream(bitstream))
        self.val = int.from_bytes(bitstream, signed=False)

    def to_bits(self):
        super().to_bits()
        return self.to_bitstream(self.val)


@dataclass
class Chr5TedsElement(BasicTedsElement):
    val: Any = ""

    def from_bits(self, bitstream):
        self.val = ""
        for i in range(0, len(bitstream), 5):
            cur_val = bitstream.read(5)
            cur_char = self.reverse_bitstream(self.zero_pad_bitstream(cur_val))
            # https://stackoverflow.com/questions/23199733/convert-numbers-into-corresponding-letter-using-python
            self.val += chr(ord("`") + int.from_bytes(cur_char, signed=False))

    def to_bits(self):
        super().to_bits()
        val = ""
        for char in self.val:
            char_val = (bin(ord(char)))[2:]
            val = val + char_val.zfill(5)[-5:][::-1]
        return Bits(bin=val)


@dataclass
class AsciiTedsElement(BasicTedsElement):
    val: Any = ""

    def from_bits(self, bitstream):
        self.val = ""
        for i in range(
            0, len(bitstream), 7
        ):  # TODO: Smarter to check if 0b0000000?
            if bitstream.len - bitstream.pos >= 7:
                cur_val = bitstream.read(7)
                cur_char = self.reverse_bitstream(
                    self.zero_pad_bitstream(cur_val)
                )
                # https://stackoverflow.com/questions/23199733/convert-numbers-into-corresponding-letter-using-python
                self.val += chr(int.from_bytes(cur_char, signed=False))

    def to_bits(self):
        super().to_bits()
        val = ""
        for char in self.val:
            # https://stackoverflow.com/questions/23199733/convert-numbers-into-corresponding-letter-using-python
            char_val = (bin(ord(char)))[2:]
            val = val + char_val.zfill(7)[::-1]
        return Bits(bin=val)


@dataclass
class DateTedsElement(BasicTedsElement):
    val: Any = None

    def from_bits(self, bitstream):
        bitstream = self.reverse_bitstream(self.zero_pad_bitstream(bitstream))
        self.val = datetime(1998, 1, 1) + timedelta(
            days=int.from_bytes(bitstream, signed=False)
        )

    def to_bits(self):
        super().to_bits()
        date_val = self.val - datetime(1998, 1, 1)
        return self.to_bitstream(date_val.days)


@dataclass
class SingleTedsElement(BasicTedsElement):

    def from_bits(self, bitstream):
        raise NotImplementedError()

    def to_bits(self):
        raise NotImplementedError()


@dataclass
class ConResTedsElement(BasicTedsElement):
    start: float
    step: float
    val: Any = None

    def from_bits(self, bitstream):
        bitstream = self.reverse_bitstream(self.zero_pad_bitstream(bitstream))
        self.val = self.start + int.from_bytes(bitstream) * self.step

    def to_bits(self):
        super().to_bits()
        int_val = (self.val - self.start) / self.step
        return self.to_bitstream(int_val)


@dataclass
class ConRelResTedsElement(BasicTedsElement):
    start: float
    step: float
    val: Any = None

    def from_bits(self, bitstream):
        # Found from tdl pdf
        bitstream = self.reverse_bitstream(self.zero_pad_bitstream(bitstream))
        self.val = self.start * (1 + 2 * self.step) ** int.from_bytes(
            bitstream
        )

    def to_bits(self):
        super().to_bits()
        int_val = math.log(self.val / self.start) / math.log(1 + 2 * self.step)
        return self.to_bitstream(int_val)


@dataclass
class EnumTedsElement(BasicTedsElement):
    options: enum.IntEnum
    val: Any = None

    def from_bits(self, bitstream):
        raise NotImplementedError()

    def to_bits(self):
        raise NotImplementedError()


@dataclass
class ConstantTedsElement(BasicTedsElement):
    val: Any = None

    def from_bits(self, bitstream):
        pass

    def to_bits(self):
        pass
