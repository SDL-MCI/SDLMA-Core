import math
from datetime import datetime

import numpy as np
import pyuff


def direction_to_int(direction_str: str) -> int:
    """
    Helper function to map the direction to uff direction integers
    :param direction_str: The direction to convert
    """
    if direction_str == "Scalar":
        return 0
    elif direction_str == "+X":
        return 1
    elif direction_str == "-X":
        return -1
    elif direction_str == "+Y":
        return 2
    elif direction_str == "-Y":
        return -2
    elif direction_str == "+Z":
        return 3
    elif direction_str == "-Z":
        return -3
    else:
        ValueError("Not implemented")


class SDLMAUFF:

    def __init__(self, name, filename=None):
        self.filename = filename
        self.pyuff = pyuff.UFF(filename)
        self.name = name
        self.nodes_to_names = {}
        if 151 not in self.pyuff.get_set_types():
            self.write_header()

    def write_header(self):
        """
        Method to write uff file header
        """
        now = datetime.now()

        date_db_created = now.strftime("%d-%b-%y")
        time_db_created = now.strftime("%H:%M:%S")

        dataset = pyuff.prepare_151(
            model_name="Test",
            description="No",
            db_app="SDLMA",
            date_db_created=date_db_created,
            time_db_created=time_db_created,
            version_db1=0,
            version_db2=0,
            file_type=0,
            date_db_saved=date_db_created,
            time_db_saved=time_db_created,
            program="SDLMA",
            date_db_written=date_db_created,
            time_db_written=time_db_created,
        )
        self.pyuff._write_set(dataset, "add")

    def write_coord_system(self):
        """
        Method to write uff file coordinate system
        """
        # At current stage not implemented in correct format
        # coord = [np.array([[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])]
        # dataset = pyuff.prepare_2420(Part_UID=1, Part_Name="Test",
        #                              CS_sys_labels=[1], CS_types=[0],
        #                              CS_colors=[8], CS_names=['CS Main'],
        #                              CS_matrices=coord)
        #
        # dataset["nodes"] = dataset["CS_matrices"]
        # self.pyuff._write_set(dataset, 'add')

        if 2420 not in self.pyuff.get_set_types():
            with open(self.filename, "at") as f:
                f.write("    -1\n")
                f.write("  2420\n")
                f.write("         1\n")
                f.write("Name\n")
                f.write("         1         0         8\n")
                f.write("Coord 1\n")
                f.write(
                    "   1.0000000000000000e+00   0.0000000000000000e+00   0.0000000000000000e+00\n"
                )
                f.write(
                    "   0.0000000000000000e+00   1.0000000000000000e+00   0.0000000000000000e+00\n"
                )
                f.write(
                    "   0.0000000000000000e+00   0.0000000000000000e+00   1.0000000000000000e+00\n"
                )
                f.write("    -1\n")

    def write_units(self):
        """
        Method to write default metric units to the uff file
        """
        dataset = pyuff.prepare_164(
            units_code=1,
            units_description="metric",
            temp_mode=1,
            length=1.0,
            force=1.0,
            temp=1.0,
            temp_offset=1.0,
        )
        if 164 not in self.pyuff.get_set_types():
            self.pyuff._write_set(dataset, "add")

    def write_nodes(self, nodes: list):
        """
        Method to write nodes in the uff file
        All nodes are currently referenced to global main coordinate system.
        :param nodes: List of nodes
        """
        node_nums = []
        def_cs = []
        disp_cs = []
        color = []
        x = []
        y = []
        z = []
        for i in range(0, len(nodes)):
            node_nums.append(i + 1)
            def_cs.append(0)
            disp_cs.append(0)
            color.append(0)
            x.append(nodes[i][0])
            y.append(nodes[i][1])
            z.append(nodes[i][2])
        dataset = pyuff.prepare_15(
            node_nums=node_nums,
            def_cs=def_cs,
            disp_cs=disp_cs,
            color=color,
            x=x,
            y=y,
            z=z,
        )
        if 15 not in self.pyuff.get_set_types():
            self.pyuff._write_set(dataset, "add")

    def write_mesh(self, lines: list[list], faces: list[list]):
        """
        Method to write the mesh for the nodes in the uff file
        :param lines: List of line elements
        :param faces: List of triangles and quad elements
        """
        if 2412 not in self.pyuff.get_set_types():
            with open(self.filename, "at") as f:
                f.write("    -1\n")
                f.write("  2412\n")
                cnt = 0
                for i in range(len(faces)):
                    cnt = cnt + 1
                    elem = 94 if len(faces[i]) == 4 else 91
                    f.write(
                        f"{cnt:10d}{elem:10d}{0:10d}{0:10d}{0:10d}{len(faces[i]):10d}\n"
                    )
                    for node in faces[i]:
                        f.write(f"{node + 1:10d}")
                    f.write("\n")
                for i in range(len(lines)):
                    cnt = cnt + 1
                    f.write(f"{cnt:10d}{11:10d}{0:10d}{0:10d}{1:10d}{2:10d}\n")
                    f.write(f"{0:10d}{1:10d}{1:10d}\n")
                    for node in lines[i]:
                        f.write(f"{node + 1:10d}")
                    f.write("\n")
                f.write("    -1\n")


    def write_frfs(self, sdlma_ema: object, mp_to_node: dict):
        """
        Method to write frfs into the uff file!
        Currently measured, maybe change to reconstructed!

        :param sdlma_ema: The sdlma_ema object that holds all frfs
        :param mp_to_node: The translation from mp in the sdlma_ema object
        to the node number
        """
        if 58 not in self.pyuff.get_set_types():
            for measurement in sdlma_ema.measurements:
                reference_node = mp_to_node[measurement.exc[0]["name"]]
                reference_direction = direction_to_int(
                    measurement.exc[0]["direction"]
                )
                frf_object = measurement.frf_object.get_FRF(
                    "H1", form="accelerance"
                )
                frequency = measurement.frf_object.get_f_axis()[1:]
                for i, signal in enumerate(measurement.resp):
                    response_node = mp_to_node[signal["name"]]
                    response_direction = direction_to_int(signal["direction"])
                    displacement_complex = frf_object[i, 0, 1:]
                    name = "TestCase"
                    dataset = pyuff.prepare_58(
                        binary=0,
                        func_type=4,
                        rsp_node=response_node,
                        rsp_dir=response_direction,
                        ref_node=reference_node,
                        ref_dir=reference_direction,
                        data=displacement_complex,
                        x=frequency,
                        id1="id1",
                        rsp_ent_name=name,
                        ref_ent_name=name,
                        abscissa_spacing=1,
                        abscissa_spec_data_type=18,
                        ordinate_spec_data_type=8,
                        orddenom_spec_data_type=13,
                    )
                    self.pyuff._write_set(dataset, "add")

    def write_modes(self, sdlma_ema, mp_to_node):
        """
        Method to write the modes to the uff file.
        :param sdlma_ema: The sdlma_ema object that holds all modes for all
        nodes
        :param mp_to_node: The translation from mp in the sdlma_ema object
        to the node number
        """
        if 55 not in self.pyuff.get_set_types():
            resp_list = []
            j = 0

            for measurement in sdlma_ema.measurements:
                for resp in measurement.resp:
                    node = mp_to_node[resp["name"]]
                    resp_list.append((j, node, resp["direction"]))
                    j += 1

            # Sort by node and channel index
            resp_list.sort(key=lambda x: (x[1], x[0]))
            for i, freq in enumerate(sdlma_ema.nat_freq):
                name = f"Mode {i + 1} at {freq} Hz"
                r1, r2, r3, r4, r5, r6, node_nums = [], [], [], [], [], [], []
                for j, node, direction in resp_list:
                    val = sdlma_ema.phi[j][i]
                    x = y = z = 0.0 + 0.0j

                    if "X" in direction:
                        x = val if direction == "+X" else -val
                    elif "Y" in direction:
                        y = val if direction == "+Y" else -val
                    elif "Z" in direction:
                        z = val if direction == "+Z" else -val

                    r1.append(x)
                    r2.append(y)
                    r3.append(z)
                    r4.append(0.0)
                    r5.append(0.0)
                    r6.append(0.0)
                    node_nums.append(node)

                dataset = pyuff.prepare_55(
                    model_type=1,
                    id1="NONE",
                    id2="NONE",
                    id3="NONE",
                    id4="NONE",
                    id5=name,
                    analysis_type=3,
                    data_ch=2,
                    spec_data_type=12,
                    data_type=5,
                    n_data_per_node=3,
                    r1=r4,
                    r2=r5,
                    r3=r6,
                    r4=None,
                    r5=None,
                    r6=None,
                    node_nums=node_nums,
                    load_case=1,
                    mode_n=i + 1,
                    eig=0.0,
                    modal_a=0.0,
                    modal_b=0.0,
                )
                # Ugly workaround because prepare does not match write
                dataset["r1"] = r1
                dataset["r2"] = r2
                dataset["r3"] = r3
                dataset["eig"] = 0.0 + freq * 2j * math.pi
                self.pyuff._write_set(dataset, "add")

    def get_points(self):
        data = self.pyuff.read_sets()
        return data
