# SDLMA-Core

Package that provides all the necessary capabilities to perform an EMA.

## Notice
This project depends on the open source efforts of [sdypy](https://github.com/sdypy/sdypy) and wouldn"t
have been possible without it.

## Installation
```bash
pip install sdlma-core
```

## Usage
The project can be utilized with finished GUI, or as a standalone.
Currently, no examples have been created!
The GUI can be found on [SDLMA-GUI](https://github.com/SDL-MCI/SDLMA-GUI)

## Create Virtual teds files
```python
from sdlma_teds import teds, teds_element
# Additional settings that can be added at own risk. Check TEDS Templates!
additional_settings = {
    "tf_hp_s": teds_element.ConRelResTedsElement(len=8, start=0.005, step=0.03, val=0.24800645070661656),
    "direction": teds_element.UnIntTedsElement(len=2, val=0),
    "transducer_weight": teds_element.ConRelResTedsElement(len=6, start=0.1, step=0.1, val=4.600511990936967)}

teds_info = teds.StandardTeds.standard_accel_force_template(manufacturer_id=16, model_number=4506, serial_number=30000,
                                                            acceleration_force=0, sens_ref=0.09785849228848621,
                                                            additional_settings=None)
teds.StandardTeds.write_teds_to_file(teds_info.teds, "test.ted")
```