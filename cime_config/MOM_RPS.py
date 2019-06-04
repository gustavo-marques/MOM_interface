from __future__ import print_function
from collections import OrderedDict
import os
import abc
import re

class MOM_RPS(object,):
    """ Base class for MOM6 (R)untime (P)arameter (S)ystem files including:
            - Params files (MOM_input, MOM_override, user_nl_mom)
            - MOM_namelist (input.nml)
            - diag_table
    """

    def __init__(self, input_path, input_format="json", output_path=None, output_format=None):
        self.input_file_read = False
        self.input_path = input_path
        self.input_format = input_format
        self.data = None

        self.read()

    def _read_json(self):
        import json
        with open(self.input_path) as json_file:
            self.data = json.load(json_file, object_pairs_hook=OrderedDict)
        self.input_file_read = True

    def _check_json_consistency(self):
        #TODO
        pass

    def apply_constraints(self, case):
        """ For a variable, if multiple values are provided in a value list, this function
            determines the appropriate value for the case by looking at constraints
            (guards) to the left of values in yaml file and by comparing them against
            the xml variable of the case, e.g. OCN_GRID."""

        if not self.data:
            raise RuntimeError("Cannot apply the constraints. No data found.")

        def _constraint_satisfied(constr_pair, case):
            " Checks if a given value constraint agrees with a given constaints basse"
            constr_key = constr_pair.split('==')[0].strip()\
                .replace('"','').replace("'","")
            constr_val = constr_pair.split('==')[1].strip()\
                .replace('"','').replace("'","")

            try:
                case_val = case.get_value(constr_key)
            except:
                raise RuntimeError("Cannot find the constraint "+constr_key+" in xml files")

            return case_val == constr_val

        for module in self.data:
            for var in self.data[module]:

                # (list of) potential value(s) for this variable.
                # maybe a single entry or multiple constrainted entries
                value_entry = self.data[module][var]["value"]

                # current applicable value for this variable:
                val = None

                # single value with no constraints:
                if not (type(value_entry)==dict or type(value_entry)==OrderedDict):
                    val = value_entry

                # single or multiple value(s) with contraint(s):
                else:
                    for value_constraints in value_entry:
                        if value_constraints == "common":
                            val = value_entry[value_constraints]

                        # multiple constraint pairs in value_constraints
                        elif ',' in value_constraints:
                            agrees = True
                            for constr_pair in value_constraints.split(','):
                                agrees = agrees and _constraint_satisfied(constr_pair, case)
                            if agrees: # with all constaints:
                                val = value_entry[value_constraints]

                        # a single constraint pair in value_constraints:
                        elif '==' in value_constraints:
                            if _constraint_satisfied(value_constraints, case):
                                val = value_entry[value_constraints]

                        else:
                            raise RuntimeError("Cannot parse configurations for variable "+var)

                self.data[module][var]['final_val'] = str(val)

    def deduce_special_vals(self, case):
        """ Replaces the values defined with special keys, i.e., ${XML_VAR}, in yaml files"""
        for module in self.data:
            for var in self.data[module]:
                val = self.data[module][var]['final_val']
                special_keys_list = re.findall(r'\$\{.+?\}',val)
                for special_key in special_keys_list:
                    special_key_strip = special_key.replace("$","").replace("{","").replace("}","")
                    special_val = case.get_value(special_key_strip)
                    if special_val==None:
                        raise RuntimeError("The constraint "+special_key_strip+" is not a CIME xml"
                                           " variable for this case")
                    val = val.replace(special_key,special_val)
                self.data[module][var]['final_val'] = val

    @abc.abstractmethod
    def check_consistency(self):
        pass

    @abc.abstractmethod
    def read(self):
        raise NotImplementedError("read function must be implemented in the derived class.")


class MOM_input_nml(MOM_RPS):

    def read(self):
        assert self.input_format=="json", "input.nml file defaults can only be read from a json file."
        self._read_json()
        self._check_json_consistency()

    def write(self, output_path, case):
        assert self.input_format=="json", "input.nml file can only be generated from a json input file."

        # Apply the constraints on the general data to get the targeted values
        self.apply_constraints(case)

        # Replace special xml values (e.g., $INPUTDIR) with their actual values
        self.deduce_special_vals(case)

        with open(os.path.join(output_path), 'w') as input_nml:
            for module in self.data:
                input_nml.write("&"+module+"\n")

                for var in self.data[module]:
                    val = self.data[module][var]["final_val"]
                    if val==None:
                        continue
                    input_nml.write("    "+var+" = "+str(self.data[module][var]["final_val"])+"\n")

                input_nml.write('/\n\n')

class Input_data_list(MOM_RPS):

    def read(self):
        assert self.input_format=="json", "input_data_list file defaults can only be read from a json file."
        self._read_json()
        self._check_json_consistency()

    def write(self, output_path, case, add_params=dict()):
        assert self.input_format=="json", "input_data_list file defaults can only be read from a json file."

        # Apply the constraints on the general data to get the targeted values
        self.apply_constraints(case)

        # Replace special xml values (e.g., $INPUTDIR) with their actual values
        self.deduce_special_vals(case)

        with open(os.path.join(output_path), 'w') as input_data_list:
            for module in self.data:
                for var in self.data[module]:
                    input_data_list.write(var+" = "+str(self.data[module][var]["final_val"])+"\n")


class MOM_Params(MOM_RPS):
    """ Encapsulates data and methods for MOM6 case parameter files with the following formats:
        MOM_input, user_nl, json.
    """

    supported_formats = ["MOM_input", "user_nl", "json"]

    def __init__(self, input_path, input_format="json"):
        MOM_RPS.__init__(self, input_path, input_format)

        if self.input_format not in MOM_Params.supported_formats:
            raise RuntimeError("MOM parameter file format "+file_format+\
                                " not supported")

    def read(self):
        if self.input_format == "MOM_input":
            self._read_MOM_input()
        elif self.input_format == "user_nl":
            self._read_user_nl()
        elif self.input_format == "json":
            self._read_json()
            self._check_json_consistency()


    def _read_MOM_input(self):
        #TODO
        pass

    def _read_user_nl(self):
        #TODO
        pass

    def write(self, output_path, case, add_params=dict()):
        """ writes a MOM_input file from a given json parameter file in accordance with
            the constraints and additional parameters that are passed. """

        assert self.input_format=="json", "MOM_input file can only be generated from a json input file."


        # Apply the constraints on the general data to get the targeted values
        self.apply_constraints(case)

        # Replace special xml values (e.g., $INPUTDIR) with their actual values
        self.deduce_special_vals(case)

        # 2. Now, write MOM_input

        MOM_input_header =\
        """/* WARNING: DO NOT EDIT this file. Any changes you make will be overriden. To make
        changes in MOM6 parameters within CESM framework, use SourceMods or
        user_nl_mom mechanisms.

        This input file provides the adjustable run-time parameters for version 6 of
        the Modular Ocean Model (MOM6), a numerical ocean model developed at NOAA-GFDL.
        Where appropriate, parameters use usually given in MKS units.

        This MOM_input file contains the default configuration for CESM. A full list of
        parameters for this example can be found in the corresponding
        MOM_parameter_doc.all file which is generated by the model at run-time. */\n\n"""

        with open(os.path.join(output_path), 'w') as MOM_input:

            MOM_input.write(MOM_input_header)

            tab = " "*32
            for module in self.data:

                # Begin module block:
                if module != "Global":
                    MOM_input.write(module+"%\n")

                for var in self.data[module]:
                    val = self.data[module][var]["final_val"]
                    if val==None:
                        continue

                    # write "variable = value" pair
                    MOM_input.write(var+" = "+str(self.data[module][var]["final_val"])+"\n")

                    # Write the variable description:
                    var_comments = self.data[module][var]["description"].split('\n')
                    if len(var_comments[-1])==0:
                        var_comments.pop()
                    for line in var_comments:
                         MOM_input.write(tab+"! "+line+"\n")
                    MOM_input.write("\n")

                # End module block:
                if module != "Global":
                    MOM_input.write("%"+module+"\n")

