#!/usr/bin/env python
""" List software licences for a given workflow """

from __future__ import print_function

import logging
import json
import re
import requests
import sys
import tabulate
import yaml

import nf_core.lint

class WorkflowLicences():
    """ Class to hold all licence info """

    def __init__(self, pipeline, json=False):
        """ Set class variables """
        self.pipeline = pipeline
        if self.pipeline.startswith('nf-core/'):
            self.pipeline = self.pipeline[8:]
        self.json = json
        self.conda_package_licences = {}

    def fetch_conda_licences(self):
        """ Get the conda licences """
        env_url = 'https://raw.githubusercontent.com/nf-core/{}/master/environment.yml'.format(self.pipeline)
        response = requests.get(env_url)

        # Check that the pipeline exists
        if response.status_code == 404:
            logging.error("Couldn't find pipeline nf-core/{}".format(self.pipeline))
            sys.exit(1)

        lint_obj = nf_core.lint.PipelineLint(self.pipeline)
        lint_obj.conda_config = yaml.load(response.text)
        # Check conda dependency list
        for dep in lint_obj.conda_config.get('dependencies', []):
            try:
                if isinstance(dep, str):
                    lint_obj.check_anaconda_package(dep)
                elif isinstance(dep, dict):
                    lint_obj.check_pip_package(dep)
            except ValueError:
                logging.error("Couldn't get licence information for {}".format(dep))

        for dep, data in lint_obj.conda_package_info.items():
            try:
                depname, depver = dep.split('=', 1)
                licences = set()
                # Licence for each version
                for f in data['files']:
                    if not depver or depver == f.get('version'):
                        try:
                            licences.add(f['attrs']['license'])
                        except KeyError:
                            pass
                # Main licence field
                if len(list(licences)) == 0 and isinstance(data['license'], basestring):
                    licences.add(data['license'])
                self.conda_package_licences[dep] = self.clean_licence_names(list(licences))
            except KeyError:
                pass

    def clean_licence_names(self, licences):
        """ Normalise varying licence names """
        clean_licences = []
        for l in licences:
            l = re.sub(r'GNU General Public License v\d \(([^\)]+)\)', r'\1', l)
            l = re.sub(r'GNU GENERAL PUBLIC LICENSE', 'GPL', l, flags=re.IGNORECASE)
            l = l.replace('GPL-', 'GPLv')
            l = re.sub(r'GPL(\d)', r'GPLv\1', l)
            l = re.sub(r'GPL \(([^\)]+)\)', r'GPL \1', l)
            l = re.sub(r'GPL\s*v', 'GPLv', l)
            l = re.sub(r'\s*(>=?)\s*(\d)', r' \1\2', l)
            clean_licences.append(l)
        return clean_licences

    def print_licences(self):
        """ Print the fetched information """

        logging.info("""Warning: This tool only prints licence information for the software tools packaged using conda.
        The pipeline may use other software and dependencies not described here. """)

        if self.json:
            print(json.dumps(self.conda_package_licences, indent=4))

        else:
            licence_list = []
            for dep, licences in self.conda_package_licences.items():
                depname, depver = dep.split('=', 1)
                try:
                    depname = depname.split('::')[1]
                except IndexError:
                    pass
                licence_list.append([depname, depver, ', '.join(licences)])
            # Sort by licence, then package name
            licence_list = sorted(sorted(licence_list), key=lambda x: x[2])
            # Print summary table
            print("", file=sys.stderr)
            print(tabulate.tabulate(licence_list, headers=['Package Name', 'Version', 'Licence']))
            print("", file=sys.stderr)