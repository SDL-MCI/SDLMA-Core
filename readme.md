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

## Example usage without GUI
```python
import os

from src import SDLMAEMA, SDLMAMeasurement, SDLMAUFF

## Preamble
search_dir = "C:/Users/Users/meas/in"
out_dir = "C:/Users/Users/meas/out"
freq_estimates = [19.8, 25.5, 48, 50.3, 72.3, 83.4, 95.3]
sdlma_ema = SDLMAEMA(10, 100, 35, "lscf", freq_estimates)

## Load Measurements
for root, dirs, files in os.walk(search_dir):
    for file in files:
        if file.endswith(".h5"):
            file_path = os.path.join(root, file)
            sdlma_measurement = SDLMAMeasurement.import_from_hd5f_file(file_path)
            sdlma_ema.add_measurement(sdlma_measurement)

## Perform EMA
sdlma_ema.calc()
sdlma_ema.get_poles()
sdlma_ema.select_poles()
sdlma_ema.export_to_hd5f_file(out_dir + "/test.h5")

## Meshing
nodes = [[-0.290794, 0.350000, 0.0],  #
         [-0.439634, 0.216409, 0.0],  #
         [-0.096931, 0.350000, 0.0],  #
         [0.096931, 0.350000, 0.0],  #
         [0.290794, 0.350000, 0.0],  #
         [0.439634, 0.216409, 0.0],  #
         [0.588474, 0.082818, 0.0],  #
         [0.458983, -0.061455, 0.0],  #
         [0.329491, -0.205727, 0.0],  #
         [0.200000, -0.350000, 0.0],  #
         [0.000000, -0.350000, 0.0],  #
         [-0.200000, -0.350000, 0.0],  #
         [-0.312949, -0.205727, 0.0],  #
         [-0.458983, -0.061455, 0.0],  #
         [-0.588474, 0.082818, 0.0],  #
         ]

# Referring to node index
lines = [[14, 1], [1, 0], [0, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7],
         [7, 8], [8, 9], [9, 10], [10, 11], [11, 12], [12, 13], [13, 14]]
faces = [[0, 12, 14], [0, 14, 3], [4, 2, 6], [4, 8, 6], [11, 13, 9],
         [7, 9, 11]]


## Post Processing 
mp_to_node = {
    'MP1': 1, 'MP2': 2, 'MP5': 3, 'MP7': 4, 'MP9': 5, 'MP11': 6, 'MP12': 7,
    'MP14': 8, 'MP21': 9, 'MP22': 10,
    'MP26': 11, 'MP27': 12, 'MP31': 13, 'MP32': 14, 'MP33': 15}


if os.path.exists(out_dir + "/test.unv"):
    os.remove(out_dir + "/test.unv")

sdlma_uff = SDLMAUFF("test", out_dir + "/test.unv")

sdlma_uff.write_coord_system()
sdlma_uff.write_units()
sdlma_uff.write_nodes(nodes)
sdlma_uff.write_mesh(
    lines,
    faces,
)
sdlma_uff.write_modes(sdlma_ema, mp_to_node)

```