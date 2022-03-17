'''
Copyright 2022 Airbus SAS

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''
'''
mode: python; py-indent-offset: 4; tab-width: 8; coding: utf-8
'''
from itertools import product
from numpy import can_cast, arange, isin
from uuid import uuid4

from sos_trades_core.api import get_sos_logger
from sos_trades_core.tools.tree.treeview import TreeView
from sos_trades_core.execution_engine.sos_discipline import SoSDiscipline

from copy import copy
from sos_trades_core.tools.tree.serializer import DataSerializer

TYPE = SoSDiscipline.TYPE
VALUE = SoSDiscipline.VALUE
RANGE = SoSDiscipline.RANGE
ORIGIN = SoSDiscipline.ORIGIN
DEFAULT = SoSDiscipline.DEFAULT
OPTIONAL = SoSDiscipline.OPTIONAL
COUPLING = SoSDiscipline.COUPLING
EDITABLE = SoSDiscipline.EDITABLE
IO_TYPE = SoSDiscipline.IO_TYPE
IO_TYPE_IN = SoSDiscipline.IO_TYPE_IN
IO_TYPE_OUT = SoSDiscipline.IO_TYPE_OUT
COMPOSED_OF = SoSDiscipline.COMPOSED_OF
NS_REFERENCE = SoSDiscipline.NS_REFERENCE
POSSIBLE_VALUES = SoSDiscipline.POSSIBLE_VALUES
INTERNAL_VISIBILITY = SoSDiscipline.INTERNAL_VISIBILITY
DISCIPLINES_DEPENDENCIES = SoSDiscipline.DISCIPLINES_DEPENDENCIES
VAR_NAME = SoSDiscipline.VAR_NAME
DATAFRAME_DESCRIPTOR = SoSDiscipline.DATAFRAME_DESCRIPTOR
DATAFRAME_EDITION_LOCKED = SoSDiscipline.DATAFRAME_EDITION_LOCKED
TYPE_METADATA = SoSDiscipline.TYPE_METADATA


class DataManager:
    """
    Specification: DataManager class collects inputs/outputs and disciplines
    """
    VALUE = 'value'
    DISC_REF = 'reference'
    STATUS = 'status'

    def __init__(self, name,
                 root_dir=None,
                 rw_object=None,
                 study_filename=None,
                 ns_manager=None,
                 logger=None):
        '''
        Constructor
        '''
        self.no_change = True
        self.name = name
        self.rw_object = rw_object
        self.root_dir = root_dir
        self.study_filename = study_filename
        self.ns_manager = ns_manager
        self.data_dict = None
        self.data_id_map = None
        self.disciplines_dict = None
        self.disciplines_id_map = None
        self.treeview = None
        self.reset()

        if logger is None:
            self.logger = get_sos_logger('SoS.EE.DataManager')
        else:
            self.logger = logger

    @staticmethod
    def get_an_uuid():
        ''' generate a random UUID to make data_dict keys unique '''
        return str(uuid4())

    def reset(self):
        self.data_dict = {}
        self.data_id_map = {}
        self.data_cache = {}
        self.disciplines_dict = {}
        self.disciplines_id_map = {}

    def get_data(self, var_f_name, attr=None):
        ''' Get attr value of var_f_name or all data_dict value of var_f_name (if attr=None)
        '''
        if attr is None:
            return self.data_dict[self.get_data_id(var_f_name)]
        else:
            return self.data_dict[self.get_data_id(var_f_name)][attr]

    def delete_complex_in_df_and_arrays(self):

        for dataa in self.data_dict.values():
            if dataa['type'] == 'dataframe' and dataa[self.VALUE] is not None:
                for col in dataa[self.VALUE].columns:
                    dataa[self.VALUE][col] = dataa[self.VALUE][col].values.real
            elif dataa['type'] == 'array':
                try:
                    dataa[self.VALUE] = dataa[self.VALUE].real
                except:
                    pass

    def check_data_in_dm(self, var_f_name):
        '''
        Check if the data is in the DM with its full name 

        :params: var_f_name, full variable name to check 
        :type : string 

        :returns: boolean True or False 
        '''
        data_in_dm = False

        if var_f_name in self.data_id_map:
            if self.get_data_id(var_f_name) in self.data_dict:
                data_in_dm = True

        return data_in_dm

    def set_data(self, var_f_name, attr, val, check_value=True):
        ''' Set attr value of var_f_name in data_dict 
        '''
        if self.get_data_id(var_f_name) in self.data_dict:
            if check_value:
                if self.data_dict[self.get_data_id(var_f_name)][attr] != val:
                    self.data_dict[self.get_data_id(var_f_name)][attr] = val
                    self.no_change = False
            else:
                self.data_dict[self.get_data_id(var_f_name)][attr] = val
        else:
            msg = f"Try to update metadata of variable {var_f_name} that does"
            msg += f" not exists as I/O of any discipline"
            raise KeyError(msg)

    def get_io_data_of_disciplines(self, disciplines):
        ''' get i/o value and metadata of provided disciplines
        '''
        data = {}
        data[VALUE] = {}
        data[TYPE_METADATA] = {}
        data["local_data"] = {}
        for d in disciplines:
            # input values and metadata
            var_list = d.get_data_io_dict_keys(io_type=IO_TYPE_IN)
            for v in var_list:
                fname = d.get_var_full_name(v, d.get_data_in())
                data[VALUE][fname] = self.get_data(fname, VALUE)
                data[TYPE_METADATA][fname] = self.get_data(
                    fname, TYPE_METADATA)
            # output values and metadata
            var_list = d.get_data_io_dict_keys(io_type=IO_TYPE_OUT)
            for v in var_list:
                fname = d.get_var_full_name(v, d.get_data_out())
                data[VALUE][fname] = self.get_data(fname, VALUE)
                data[TYPE_METADATA][fname] = self.get_data(
                    fname, TYPE_METADATA)
            # local data update
            data["local_data"].update(d.local_data)
        return data

    def get_value(self, var_f_name):
        ''' Get value of var_f_name from data_dict 
        '''
        return self.get_data(var_f_name, SoSDiscipline.VALUE)

    def get_discipline(self, disc_id):
        ''' Get discipline with disc_id from disciplines_dict 
        '''
        if disc_id in self.disciplines_dict:
            return self.disciplines_dict[disc_id][self.DISC_REF]
        else:
            return None

    def get_disciplines_with_name(self, disc_f_name):
        ''' Get discipline with disc_id from disciplines_dict 
        '''
        disc_list = []
        disc_id_list = self.get_discipline_ids_list(disc_f_name)

        for disc_id in disc_id_list:
            disc_list.append(self.disciplines_dict[disc_id][self.DISC_REF])

        return disc_list

    def get_all_namespaces_from_var_name(self, var_name):
        ''' Get all namespaces containing var_name in data_dict 
        '''
        namespace_list = []
        for key in self.data_id_map.keys():
            if key.endswith('.' + var_name):
                namespace_list.append(key)

        return namespace_list

    def get_all_var_name_with_ns_key(self, var_name):
        ''' Get all namespaces containing var_name in data_dict plus their namespace key as a dict
        '''
        namespace_list = []
        for key in self.data_id_map.keys():
            if key.endswith('.' + var_name):
                namespace_list.append(key)
        if len(namespace_list) > 0:
            ns_dict_obj = self.get_data_dict_attr('ns_reference')
            return {ns: ns_dict_obj[ns].name for ns in namespace_list}
        else:
            return {}

    def get_data_id(self, var_f_name):
        ''' Get data id with var_f_name
        '''
        return self.data_id_map[var_f_name]

    def get_discipline_ids_list(self, disc_f_name):
        ''' Get discipline id list with disc_f_name
        '''
        return self.disciplines_id_map[disc_f_name]

    def generate_data_id_map(self):
        ''' Generate data_id_map with data_dict
        '''
        self.data_id_map = {}
        data_dict = copy(self.data_dict)
        for var_id in data_dict.keys():
            var_f_name = self.get_var_full_name(var_id)
            self.data_id_map[var_f_name] = var_id

    def generate_disciplines_id_map(self):
        ''' Generate disciplines_id_map with disciplines_dict
        '''
        self.disciplines_id_map = {}
        for disc_id in self.disciplines_dict.keys():
            disc_f_name = self.get_disc_full_name(disc_id)
            self.add_disc_id_to_disc_id_map(disc_f_name, disc_id)

    def set_values_from_dict(self, values_dict, full_ns_keys=True):
        ''' Set values in data_dict from dict with namespaced keys 
            if full_ns_keys (not uuid), try to get its uuid correspondency through get_data_id function
        '''
        keys_to_map = self.data_id_map.keys() if full_ns_keys else self.data_id_map.values()
        for key, value in values_dict.items():
            if not key in keys_to_map:
                raise ValueError(f'{key} does not exist in data manager')
            k = self.get_data_id(key) if full_ns_keys else key
            # if self.data_dict[k][SoSDiscipline.VISIBILITY] == INTERNAL_VISIBILITY:
            #     raise Exception(f'It is not possible to update the variable {k} which has a visibility Internal')
            self.data_dict[k][VALUE] = value

    def convert_data_dict_with_full_name(self):
        ''' Return data_dict with namespaced keys
        '''
        return self.convert_dict_with_maps(self.data_dict, self.data_id_map, keys='full_names')

    def get_data_dict_values(self, excepted=[]):
        '''
        Return a dictionaries with all full named keys in the dm and the value of each key from the dm 
        '''
        return self.get_data_dict_attr(self.VALUE, excepted)

    def get_data_dict_attr(self, attr, excepted=[]):
        '''
        Return a dictionaries with all full named keys in the dm and the value of each key from the dm 
        '''
        data_dict = self.convert_data_dict_with_full_name()
        exception_list = []
        if 'numerical' in excepted:
            exception_list = list(SoSDiscipline.NUM_DESC_IN.keys())

        if 'None' in excepted:
            data_dict_values = {key: value.get(attr, None)
                                for key, value in data_dict.items() if key.split('.')[-1] not in exception_list}
        else:
            data_dict_values = {key: value.get(attr, None)
                                for key, value in data_dict.items() if key.split('.')[-1] not in exception_list}

        return data_dict_values

    def get_data_dict_list_attr(self, list_attr, excepted=[]):
        """
         Return a dictionary of dictionary with all full named keys in the dm and the value of each key from the dm
         output : dict[key][attr] for each attr in list_attr
        """
        data_dict_values_dict = {}
        data_dict_values_list = [self.get_data_dict_attr(attr, excepted) for attr in list_attr]

        for key in data_dict_values_list[0].keys():
            data_dict_values_dict[key] = {}
            for index, attr in enumerate(list_attr):
                data_dict_values_dict[key][attr] = data_dict_values_list[index][key]

        return data_dict_values_dict

    def convert_data_dict_with_ids(self, dict_to_convert):
        ''' Return data_dict with ids keys
        '''
        return self.convert_dict_with_maps(dict_to_convert,
                                           self.data_id_map, keys='ids')

    def convert_disciplines_dict_with_full_name(self):
        ''' Return disciplines dict with namespaced keys
        '''

        converted_dict = {}

        for key, val in self.disciplines_id_map.items():
            if key not in converted_dict:
                converted_dict[key] = []

            if isinstance(val, list):
                for val_element in val:
                    if val_element in self.disciplines_dict:
                        converted_dict[key].append(
                            self.disciplines_dict[val_element])
            else:
                if val in self.disciplines_dict:
                    converted_dict[key].append(self.disciplines_dict[val])
        return converted_dict

    def convert_dict_with_maps(self, dict_to_convert, map_full_names_ids, keys='full_names'):
        ''' Convert dict keys with ids to full_names or full_names to ids
            keys: 'full_names' or 'ids'
        '''
        converted_dict = {}
        if keys == 'full_names':
            for key, val in map_full_names_ids.items():
                if isinstance(val, list):
                    for val_element in val:
                        if val_element in dict_to_convert:
                            # The last val_element overwrites the others ...
                            converted_dict[key] = dict_to_convert[val_element]

                else:
                    if val in dict_to_convert:
                        converted_dict[key] = dict_to_convert[val]

        elif keys == 'ids':
            for key, val in map_full_names_ids.items():
                if key in dict_to_convert:
                    if isinstance(val, list):
                        for val_element in val:
                            converted_dict[val_element] = dict_to_convert[key]
                    else:
                        converted_dict[val] = dict_to_convert[key]

        return converted_dict

    def update_with_discipline_dict(self, disc_id, disc_dict):
        ''' Store and update the discipline data into the DM dictionary
        '''
        self.logger.debug(
            f'store and update the discipline data into the DM dictionary {list(disc_dict.keys())[:10]} ...')

        def _dm_update(var_name, io_type, var_f_name):

            if var_f_name in self.data_id_map.keys():
                # If data already exists in DM
                var_id = self.get_data_id(var_f_name)
                # IO_TYPE_IN HANDLING
                if io_type == IO_TYPE_IN:
                    if self.data_dict[var_id][IO_TYPE] != IO_TYPE_OUT:
                        # reference the parameter from the data manager to the
                        # discipline
                        disc_dict[var_name] = self.data_dict[var_id]
                    # else data already exist as OUTPUT and has priority!
                    # => do nothing
                else:
                    # io_type == IO_TYPE_OUT
                    if self.data_dict[var_id][IO_TYPE] == IO_TYPE_OUT:

                        # if already existing data was an OUTPUT
                        if disc_id in self.data_dict[var_id][DISCIPLINES_DEPENDENCIES]:
                            if self.data_dict[var_id][ORIGIN] == disc_id:
                                # if same discipline: just an update
                                self.data_dict[var_id].update(
                                    disc_dict[var_name])
                                # self.no_change = False
                        else:
                            if self.get_disc_full_name(self.data_dict[var_id][ORIGIN]) is None:
                                # Quick fix to solve cases when
                                self.logger.warning(
                                    f"Discipline with id {self.data_dict[var_id][ORIGIN]} does not exist in the DM.")
                            else:
                                # Data cannot be the OUTPUT of several
                                # disciplines
                                raise ValueError(
                                    f'Model key: {self.get_var_full_name(var_id)} of discipline {self.get_disc_full_name(disc_id)} already exists from disc {self.get_disc_full_name(self.data_dict[var_id][ORIGIN])}')
                    else:
                        # Overwrite OUTPUT information over INPUT information
                        # (OUTPUT has priority)
                        disc_dict[var_name][ORIGIN] = disc_id
                        disc_dict[var_name][DISCIPLINES_DEPENDENCIES] = self.data_dict[var_id][DISCIPLINES_DEPENDENCIES]
                        self.no_change = False
                        # Fix introduced to avoid a particular problem where the input value which is properly set is
                        # overwritten by a null output.
                        # The case was encountered when loading the pickle of an optim study and on an output variable
                        # from a discipline which shared a node with another
                        # one ('techno invest level').
                        if self.data_dict[var_id][VALUE] is not None:
                            disc_dict[var_name][VALUE] = self.data_dict[var_id][VALUE]
                        self.data_dict[var_id] = disc_dict[var_name]
                if not disc_id in self.data_dict[var_id][DISCIPLINES_DEPENDENCIES]:
                    self.data_dict[var_id][DISCIPLINES_DEPENDENCIES].append(
                        disc_id)
                    self.no_change = False
            else:
                # data does not exist yet, add it DM
                disc_dict[var_name][ORIGIN] = disc_id
                disc_dict[var_name][DISCIPLINES_DEPENDENCIES] = [disc_id]
                var_id = self.get_an_uuid()
                self.no_change = False
                self.data_dict[var_id] = disc_dict[var_name]
                self.data_id_map[var_f_name] = var_id
            # END update method

        for var_name in disc_dict.keys():
            io_type = disc_dict[var_name][IO_TYPE]
            ns_reference = disc_dict[var_name][NS_REFERENCE]
            complete_var_name = disc_dict[var_name][VAR_NAME]
            var_f_name = self.ns_manager.compose_ns([ns_reference.value,
                                                     complete_var_name])
            _dm_update(var_name, io_type, var_f_name)

    def update_disciplines_dict(self, disc_id, reference, disc_f_name):
        ''' Store and update discipline into disciplines_dicts
        '''
        self.logger.debug(
            f'store the discipline instances as references for {disc_id}')

        if disc_id is not None:
            # Update already existing discipline with reference
            self.disciplines_dict[disc_id].update(reference)

        else:
            # Create new discipline with unique id in disciplines_dict
            disc_id = self.get_an_uuid()
            self.disciplines_dict[disc_id] = reference
            self.add_disc_id_to_disc_id_map(disc_f_name, disc_id)

        return disc_id

    def add_disc_id_to_disc_id_map(self, disc_f_name, disc_id):

        if disc_f_name in self.disciplines_id_map:
            self.disciplines_id_map[disc_f_name].append(disc_id)
        else:
            self.disciplines_id_map[disc_f_name] = [disc_id]

    def update_disciplines_dict_with_id(self, disc_id, reference):
        '''
        Update the discipline_dict of a specific disc_id with the dict reference
        '''
        self.disciplines_dict[disc_id].update(reference)

    def update_data_dict_with_id(self, var_id, data_dict):
        '''
        Update the discipline_dict of a specific disc_id with the dict reference
        '''
        self.no_change = False
        self.data_dict[var_id].update(data_dict)

    def create_treeview(self, root_process, process_module, no_data=False, read_only=False):
        '''
        Function that builds a composite structure
        regarding the DataManager stored data
        '''
        self.treeview = TreeView(
            name=self.name, no_data=no_data, read_only=read_only)
        self.treeview.create_tree_node(data_manager=self,
                                       root_process=root_process,
                                       process_module=process_module,
                                       ns_manager=self.ns_manager)

    def export_data_dict_and_zip(self, export_dir):
        '''
        method that exports the DM data dict to csv files
        by a treatment delegated to the TreeView class (using strategy object)

        :params: anonymize_function, a function that map a given key of the data
        dictionary using rule given by the execution engine for the saving process
        :type: function
        '''
        self.logger.debug('export data in exported csv files')
        # retrieve only key unit and value from data_dict
        dict_to_export = {}
        for k, v in self.convert_data_dict_with_full_name().items():
            dict_to_export[k] = {'unit': v.get('unit'),
                                 'value': v.get('value')}

        serializer = DataSerializer()
        return serializer.export_data_dict_and_zip(dict_to_export,
                                                   export_dir)

    def remove_keys(self, disc_id, data_d):
        ''' Clean namespaced keys in data_dict and remove discipline dependencies
        '''
        list_data_d = [data_d] if isinstance(data_d, str) else data_d

        for var_f_name in list_data_d:
            # -- Only remove variables discid is reponsible for !
            if var_f_name in self.data_id_map.keys():
                var_id = self.get_data_id(var_f_name)

                # -- Some variables has more than one dependencies on variables.
                # -- Dependencies are ketp into DISCIPLINES_DEPENDENCIES list
                # -- When asked for a remove, this list is use to determine if the discipline was one of
                # -- the dependencies and it removed from the the list.
                # -- once the list is empty the variables is removed from the data manager.

                if disc_id in self.data_dict[var_id][SoSDiscipline.DISCIPLINES_DEPENDENCIES]:
                    self.no_change = False
                    self.data_dict[var_id][SoSDiscipline.DISCIPLINES_DEPENDENCIES].remove(
                        disc_id)

                    if len(self.data_dict[var_id][SoSDiscipline.DISCIPLINES_DEPENDENCIES]) == 0:
                        # remove data in data_dict and data_id_map if no other
                        # discipline dependency
                        del self.data_dict[var_id]
                        del self.data_id_map[var_f_name]
                else:
                    pass

    def clean_from_disc(self, disc_id, clean_keys=True):
        ''' Clean disc in disciplines_dict and data_in/data_out keys in data_dict
        '''
        disc_f_name = self.get_disc_full_name(disc_id)
        if disc_f_name not in self.disciplines_id_map:
            msg = "Discipline " + str(disc_f_name) + \
                  " not found in DataManager, "
            msg += "it is not possible to delete it."
            raise KeyError(msg)

        # remove discipline in disciplines_dict and disciplines_id_map

        disc_ref = self.get_discipline(disc_id)

        if clean_keys:
            self.clean_keys(disc_id)
        else:
            keys_to_remove = []
            for key in disc_ref.DEFAULT_NUMERICAL_PARAM:
                keys_to_remove.append(
                    disc_ref._convert_to_namespace_name(key, disc_ref.IO_TYPE_IN))
            self.remove_keys(
                disc_id, keys_to_remove)

        # remove discipline in disciplines_dict and disciplines_id_map
        self.disciplines_id_map[disc_f_name].remove(disc_id)
        if len(self.disciplines_id_map[disc_f_name]) == 0:
            self.disciplines_id_map.pop(disc_f_name)
        self.disciplines_dict.pop(disc_id)

    def clean_keys(self, disc_id):
        '''
        Clean data_in/out of disc_id in data_dict
        '''
        disc_ref = self.get_discipline(disc_id)
        # clean input keys from dm
        self.remove_keys(disc_id, list(disc_ref.apply_visibility_ns(
            SoSDiscipline.IO_TYPE_IN)))
        # clean output keys from dm
        self.remove_keys(disc_id, list(disc_ref.apply_visibility_ns(
            SoSDiscipline.IO_TYPE_OUT)))

    def export_couplings(self, in_csv=False, f_name=None):
        ''' Export couplings of all disciplines registered in the DM
        '''
        d_dict = self.disciplines_dict
        # gather disciplines references
        disc_list = [d_dict[key][self.DISC_REF] for key in d_dict]
        # filter sos_couplings
        sosc_list = [disc for disc in disc_list if disc.is_sos_coupling]
        # loop on sosc and append couplings data
        if sosc_list != []:
            sosc = sosc_list.pop()
            df = sosc.export_couplings()
            for sosc in sosc_list:
                df_sosc = sosc.export_couplings()
                df = df.append(df_sosc, ignore_index=True)
            # write data or return dataframe
            if in_csv:
                # writing of the file
                if f_name is None:
                    f_name = f"{self.name}.csv"
                df.to_csv(f_name, index=False)
            else:
                return df
        else:
            return None

    def build_disc_status_dict(self, disciplines_to_keep=None):
        ''' build a containing disc/status info into dictionary) '''
        disc_status = {}
        for namespace, disciplines in self.convert_disciplines_dict_with_full_name().items():
            if namespace not in disc_status:
                disc_status[namespace] = {}

            for discipline in disciplines:
                if disciplines_to_keep is not None:
                    if discipline['reference'] in disciplines_to_keep:
                        disc_status[namespace].update(
                            {discipline['classname']: discipline[DataManager.STATUS]})
                else:
                    disc_status[namespace].update(
                        {discipline['classname']: discipline[DataManager.STATUS]})
        return disc_status

    def get_parameter_data(self, parameter_key):
        # TO DO: convert parameter_key into uid
        ''' returns BytesIO of the data value from a namespaced key based of string table format '''
        self.logger.debug(f'get BytesIO of data {parameter_key}')
        # use cache to get parameter data value
        param_data = self.convert_data_dict_with_full_name()[parameter_key]
        param_value = param_data[SoSDiscipline.VALUE]
        if param_value is None:
            return None
        else:
            serializer = DataSerializer()
            return serializer.convert_to_dataframe_and_bytes_io(param_value,
                                                                parameter_key)

    def get_var_name_from_uid(self, var_id):
        ''' Get namespace and var_name and return namespaced variable
        '''
        return self.data_dict[var_id][SoSDiscipline.VAR_NAME]

    def get_var_full_name(self, var_id):
        ''' Get namespace and var_name and return namespaced variable
        '''
        var_name = self.get_var_name_from_uid(var_id)
        ns_reference = self.data_dict[var_id][SoSDiscipline.NS_REFERENCE]
        var_f_name = self.ns_manager.compose_ns([ns_reference.value, var_name])
        return var_f_name

    def get_disc_full_name(self, disc_id):
        ''' Get full discipline name
        '''
        if disc_id in self.disciplines_dict:
            return self.disciplines_dict[disc_id][SoSDiscipline.NS_REFERENCE].value
        else:
            return None

    # -- Check if datamanager is usable or not

    def check_inputs(self, raise_exeption=True):
        '''Check if all inputs are filled
        '''
        errors_in_dm_msg = None
        for var_id in self.data_dict.keys():
            var_f_name = self.get_var_full_name(var_id)
            io_type = self.data_dict[var_id][IO_TYPE]
            vtype = self.data_dict[var_id][TYPE]
            optional = self.data_dict[var_id][OPTIONAL]
            value = self.data_dict[var_id][VALUE]
            prange = self.data_dict[var_id][RANGE]
            possible_values = self.data_dict[var_id][POSSIBLE_VALUES]

            if vtype not in SoSDiscipline.VAR_TYPE_MAP.keys():
                vtype_err = f'Variable: {var_f_name} of type {vtype} not in allowed type {list(SoSDiscipline.VAR_TYPE_MAP.keys())}'
                self.logger.error(vtype_err)
            # check if data is and input and is not optional
            if io_type == IO_TYPE_IN and not optional:
                if value is None:
                    errors_in_dm_msg = f'Variable: {var_f_name} value is not set!'
                    self.logger.error(errors_in_dm_msg)
                else:
                    if prange is not None:
                        check_range = True
                        if vtype in ['int', 'float', 'string']:

                            if not can_cast(type(value), type(prange[0])):
                                errors_in_dm_msg = f'Variable: {var_f_name}: {value} ({type(value)}) not the same as {prange[0]} ({type(prange[0])})'
                                check_range = False
                                self.logger.error(errors_in_dm_msg)
                            if not can_cast(type(value), type(prange[1])):
                                errors_in_dm_msg = f'Variable: {var_f_name}: {value} ({type(value)}) not the same as {prange[0]} ({type(prange[1])})'
                                check_range = False
                                self.logger.error(errors_in_dm_msg)
                            if check_range:
                                if prange[0] <= value <= prange[1]:
                                    pass
                                else:
                                    errors_in_dm_msg = f'Variable: {var_f_name} : {value} is not in range {prange}'
                                    self.logger.error(errors_in_dm_msg)
                        elif vtype in ['string_list', 'float_list', 'int_list']:
                            for sub_value in value:
                                if not can_cast(type(sub_value), type(prange[0])):
                                    errors_in_dm_msg = f'Variable: {var_f_name}: {sub_value} ({type(sub_value)}) in list {value} not the same as {prange[0]} ({type(prange[0])})'
                                    check_range = False
                                    self.logger.error(errors_in_dm_msg)
                                if not can_cast(type(sub_value), type(prange[1])):
                                    errors_in_dm_msg = f'Variable: {var_f_name}: {sub_value} ({type(sub_value)}) in list {value} not the same as {prange[0]} ({type(prange[0])})'
                                    check_range = False
                                    self.logger.error(errors_in_dm_msg)
                                if check_range:
                                    if prange[0] <= sub_value <= prange[1]:
                                        pass
                                    else:
                                        errors_in_dm_msg = f'Variable: {var_f_name} : {sub_value} in list {value} is not in range {prange}'
                                        self.logger.error(errors_in_dm_msg)
                        else:
                            errors_in_dm_msg = f'Variable: {var_f_name} type {vtype} does not support *range*'
                            self.logger.error(errors_in_dm_msg)
                    if possible_values is not None:
                        if vtype in ['int', 'float', 'string', 'bool']:
                            if value not in possible_values:
                                errors_in_dm_msg = f'Variable: {var_f_name} : {value} not in *possible values* {possible_values}'
                                self.logger.error(errors_in_dm_msg)
                        elif vtype in ['string_list', 'float_list', 'int_list']:
                            for sub_value in value:
                                if sub_value not in possible_values:
                                    errors_in_dm_msg = f'Variable: {var_f_name} : {sub_value} in list {value} not in *possible values* {possible_values}'
                                    self.logger.error(errors_in_dm_msg)
                        else:
                            errors_in_dm_msg = f'Variable: {var_f_name}: type {vtype} does not support *possible values*'
                            self.logger.error(errors_in_dm_msg)
                    if vtype in ['array', 'dict', 'dataframe']:
                        dataframe_descriptor = self.data_dict[var_id][DATAFRAME_DESCRIPTOR]
                        dataframe_edition_locked = self.data_dict[var_id][DATAFRAME_EDITION_LOCKED]
                        # Dataframe editable in GUI but no dataframe descriptor
                        if dataframe_descriptor is None and not dataframe_edition_locked:
                            errors_in_dm_msg = f'Variable: {var_f_name} of type {vtype} has no dataframe descriptor set'
                            self.logger.error(errors_in_dm_msg)
                        elif not dataframe_edition_locked:
                            for key in dataframe_descriptor:
                                # Check column data well described
                                if len(dataframe_descriptor[key]) != 3:
                                    errors_in_dm_msg = f'Variable: {var_f_name} of type {vtype} has a partial dataframe descriptor set up'
                                    self.logger.error(errors_in_dm_msg)
                                # Check column type authorised
                                if dataframe_descriptor[key][0] not in SoSDiscipline.VAR_TYPE_MAP.keys():
                                    errors_in_dm_msg = f'Variable: {var_f_name}, with dataframe descriptor has a column type ' \
                                                       f'{dataframe_descriptor[key][0]} not in allowed type {list(SoSDiscipline.VAR_TYPE_MAP.keys())}'
                                    self.logger.error(errors_in_dm_msg)
        has_errors_in_dm = errors_in_dm_msg is not None
        if has_errors_in_dm and raise_exeption:
            raise ValueError(
                f'DataManager contains *value errors*: {errors_in_dm_msg}')
        return has_errors_in_dm
