import platform
from collections import defaultdict
from pydantic import Field
from pydantic.dataclasses import dataclass
from enum import Enum, _EnumDict, EnumMeta
import GPUtil
from cpuinfo import get_cpu_info
from typing_extensions import Self


class StrEnumMeta(EnumMeta):
    def __new__(metacls, cls, bases, oldclassdict):
        """
        Scan through `oldclassdict` and convert any value that is a plain tuple
        into a `str` of the name instead
        """
        newclassdict = _EnumDict()
        setattr(newclassdict, "_cls_name", cls)
        for k, v in oldclassdict.items():
            if v == ():
                v = k
            newclassdict[k] = v
        return super().__new__(metacls, cls, bases, newclassdict)


class StrEnum(str, Enum, metaclass=StrEnumMeta):
    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return str(self)


class OperatingSystem(StrEnum):
    Linux = ()
    Darwin = ()
    Windows = ()


class HardwareType(StrEnum):
    CPU = ()
    GPU = ()


class HardwareVendor(StrEnum):
    GenuineIntel = ()
    Nvidia = ()


class VulkanBackend(StrEnum):
    MoltenVK = ()
    SwiftShader = ()
    Vulkan = ()


@dataclass
class HardwareInformation:
    hardware_type: HardwareType
    hardware_vendor: HardwareVendor
    hardware_model: str
    driver_version: str


@dataclass
class ExecutionPlatform:
    vulkan_backend: VulkanBackend
    operating_system: OperatingSystem = Field(
        default_factory=lambda: OperatingSystem(platform.system())
    )
    available_hardware: dict[HardwareType, list[HardwareInformation]] = Field(
        default_factory=lambda: defaultdict(list)
    )

    def __str__(self) -> str:
        return f"{self.operating_system.value}/{self.get_active_hardware().hardware_vendor.value}/{self.vulkan_backend.value}"

    def __repr__(self) -> str:
        return str(self)

    @classmethod
    def auto_detect(cls) -> Self:
        execution_platform = cls(vulkan_backend=VulkanBackend.Vulkan)
        nvidia_gpus: list[GPUtil.GPU] = GPUtil.getGPUs()
        for nvidia_gpu in nvidia_gpus:
            gpu_info: HardwareInformation = HardwareInformation(
                HardwareType.GPU,
                HardwareVendor.Nvidia,
                nvidia_gpu.name,
                nvidia_gpu.driver,
            )
            execution_platform.available_hardware[HardwareType.GPU].append(gpu_info)
        raw_cpu_info = get_cpu_info()
        cpu_info: HardwareInformation = HardwareInformation(
            HardwareType.CPU,
            HardwareVendor(raw_cpu_info["vendor_id_raw"]),
            raw_cpu_info["brand_raw"],
            "N/A",
        )
        execution_platform.available_hardware[HardwareType.CPU].append(cpu_info)

        # TODO SwiftShader is a possibility, lavapipe, llvmpipe etc.
        if execution_platform.operating_system == OperatingSystem.Darwin:
            execution_platform.vulkan_backend = VulkanBackend.MoltenVK
        elif execution_platform.operating_system == OperatingSystem.Linux:
            execution_platform.vulkan_backend = VulkanBackend.Vulkan

        return execution_platform

    def display_summary(self) -> None:
        print(f"Detected OS     -> {self.operating_system.value}")
        print(f"Detected GPUs   -> {self.available_hardware[HardwareType.GPU]}")
        print(
            f"Detected CPU    -> {self.available_hardware[HardwareType.CPU][0].hardware_model}"
        )
        print(f"Vulkan backend  -> {self.vulkan_backend.value}")
        if self.available_hardware[HardwareType.GPU]:
            print(
                f"Shaders will most likely be executed on {self.available_hardware[HardwareType.GPU][0].hardware_model}"
            )
        else:
            print("No GPU detected, shaders will be executed on CPU")

    def get_active_hardware(self) -> HardwareInformation:
        if self.available_hardware[HardwareType.GPU]:
            return self.available_hardware[HardwareType.GPU][0]
        return self.available_hardware[HardwareType.CPU][0]
