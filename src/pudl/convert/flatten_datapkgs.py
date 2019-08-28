"""This module takes a bundle of datapackages and flattens them."""

import json
import logging
import os
import pathlib
import shutil

import pudl

logger = logging.getLogger(__name__)


##############################################################################
# Flattening PUDL Data Packages
##############################################################################


def flatten_data_packages_csvs(pkg_bundle_dir, pkg_name='pudl-all'):
    """
    Copy the CSVs into a new data package directory.

    Args:
        pkg_bundle_dir (path-like): the subdirectory where the bundle of data
            packages live
        pkg_name (str): the name you choose for the flattened data package.

    """
    # set where the flattened datapackage is going to live
    all_dir = pathlib.Path(pkg_bundle_dir, pkg_name)
    # delete the subdirectory if it exists
    if os.path.exists(all_dir):
        shutil.rmtree(all_dir)
    # make the subdirectory..
    os.mkdir(all_dir)
    # we also need the sub-subdirectory for the data
    all_data_dir = pathlib.Path(pkg_bundle_dir, pkg_name, 'data')
    os.mkdir(all_data_dir)
    # for each of the package directories, copy over the csv's
    for pkg_dir in pkg_bundle_dir.iterdir():
        # copy all the csv's except not from all_dir - would make duplicates or
        # from the epacems package (because it has CEMS and EIA files).
        if pkg_dir != all_dir and pkg_dir.name != 'epacems_eia860':
            for csv in pathlib.Path(pkg_dir, 'data').iterdir():
                # if the csv already exists, shutil.copy will overrite. this is
                # fine because we've already checked if the parameters are the
                # same
                shutil.copy(csv, all_data_dir)
        # for the CEMS pacakge, only pull the actual CEMS tables.
        elif pkg_dir.name == 'epacems_eia860':
            for csv in pathlib.Path(pkg_dir, 'data').iterdir():
                shutil.copy(csv, all_data_dir)
                # if 'hourly_emissions_epacems' in csv.name:
                #    shutil.copy(csv, all_data_dir)


def compile_data_packages_metadata(pkg_bundle_dir,
                                   pkg_name='pudl-all'):
    """
    Grab the metadata from each of your dp's.

    Args:
        pkg_bundle_dir (path-like): the subdirectory where the bundle of data
            packages live
        pkg_name (str): the name you choose for the flattened data package.

    Returns:
        dict: pkg_descriptor_elements

    """
    resources = []
    pkg_descriptor_elements = {}
    for pkg_dir in pkg_bundle_dir.iterdir():
        if pkg_dir.name != pkg_name:
            with open(pathlib.Path(pkg_dir, "datapackage.json")) as md:
                metadata = json.load(md)
            if pkg_dir.name != 'epacems_eia860':
                resources.extend(metadata['resources'])
            if pkg_dir.name == 'epacems_eia860':
                resources.extend(
                    [r for r in metadata['resources']
                     if 'hourly_emissions_epacems' in r['name']])
            for thing in ['id', 'licenses', 'homepage', 'profile',
                          'created', 'sources', 'contributors']:
                try:
                    pkg_descriptor_elements[thing].append(metadata[thing])
                except KeyError:
                    pkg_descriptor_elements[thing] = [metadata[thing]]
    pkg_descriptor_elements['resources'] = resources
    return(pkg_descriptor_elements)


def flatten_data_package_metadata(pkg_bundle_dir,
                                  pkg_name='pudl-all'):
    """
    Convert a bundle of PULD data package metadata into one file.

    Args:
        pkg_bundle_dir (path-like): the subdirectory where the bundle of data
            packages live
        pkg_name (str): the name you choose for the flattened data package.

    Returns:
        dict: pkg_descriptor

    """
    # grab the peices of metadata from each of the data packages
    pkg_descriptor_elements = compile_data_packages_metadata(pkg_bundle_dir,
                                                             pkg_name=pkg_name)
    # the beginning of the data package descriptor
    pkg_descriptor = {
        'name': pkg_name,
        'title': 'flattened bundle of pudl data packages',
    }
    # the uuid for the individual data packages should be exactly the same
    if not len(set(pkg_descriptor_elements['id'])) == 1:
        raise AssertionError(
            'too many ids found in data packages metadata')
    # for these pkg_descriptor items, they should all be the same, so we are
    # just going to grab the first item for the flattened metadata
    for item in ['id', 'licenses', 'homepage']:
        pkg_descriptor[item] = pkg_descriptor_elements[item][0]
    # we're gonna grab the first 'created' timestap (each dp generates it's own
    # timestamp, which are slightly different)
    pkg_descriptor['created'] = min(pkg_descriptor_elements['created'])
    # these elements are dictionaries that have different items inside of them
    # we want to grab all of the elements and have no duplicates
    for item in ['sources', 'contributors']:
        # flatten the list of dictionaries
        list_of_dicts = \
            [item for sublist in pkg_descriptor_elements[item]
                for item in sublist]
        if item == 'contributors':
            # turn the dict elements into tuple/sets to de-dupliate it
            pkg_descriptor[item] = [dict(y) for y in set(
                tuple(x.items()) for x in list_of_dicts)]
        elif item == 'sources':
            sources_list = []
            # pull only one of each dataset creating a dictionary with the
            # dataset as the key
            for s in dict([(source['title'], source)
                           for source in list_of_dicts]).values():
                sources_list.append(s)
            pkg_descriptor['source'] = sources_list
    # we've already flattened the resources so just use that
    pkg_descriptor['resources'] = pkg_descriptor_elements['resources']
    return(pkg_descriptor)


def get_all_sources(pkg_descriptor_elements):
    """Grab list of all of the datasets in a data package bundle."""
    titles = set()
    for sources in pkg_descriptor_elements['sources']:
        for source in sources:
            titles.add(source['title'])
    return(titles)


def get_same_source_meta(pkg_descriptor_elements, title):
    """Grab the the source metadata of the same dataset from all datapackages."""
    samezies = []
    for sources in pkg_descriptor_elements['sources']:
        for source in sources:
            if source['title'] == title:
                samezies.append(source)
    return(samezies)


def check_for_matching_parameters(pkg_bundle_dir, pkg_name):
    """
    Check to see if the ETL parameters for datasets are the same across dp's.

    Args:
        pkg_bundle_dir (path-like): the subdirectory where the bundle of data
            packages live
        pkg_name (str): the name you choose for the flattened data package.
    """
    logger.info('checking for matching etl parameters across datapackages')
    # grab all of the metadata components
    pkg_descriptor_elements = compile_data_packages_metadata(pkg_bundle_dir,
                                                             pkg_name=pkg_name)
    # grab all of the "titles" (read sources)
    titles = get_all_sources(pkg_descriptor_elements)
    # check if
    for title in titles:
        samezies = get_same_source_meta(pkg_descriptor_elements, title)
        # for each of the source dictionaries, check if they are the same
        for source_dict in samezies:
            if not samezies[0] == source_dict:
                raise AssertionError(f'parameters do not match for {title}')


def flatten_pudl_datapackages(pudl_settings,
                              pkg_bundle_dir_name,
                              pkg_name='pudl-all'):
    """
    Combines a collection of PUDL data packages into one.

    Args:
        pkg_bundle_name (str): the name of the subdirectory where the bundle of
            data packages live. Normally, this name will have been generated in
            `generate_data_packages`.
        pudl_settings (dict) : a dictionary filled with settings that mostly
            describe paths to various resources and outputs.
        pkg_name (str): the name you choose for the flattened data package.

    Returns:
        dict: a dictionary of the data package validation report.

    """
    # determine the subdirectory for the package bundles...
    pkg_bundle_dir = pathlib.Path(pudl_settings['datapackage_dir'],
                                  pkg_bundle_dir_name)
    if not os.path.exists(pkg_bundle_dir):
        raise AssertionError(
            "The datapackage bundle directory does not exist. ")

    # check that data packages that have the same sources have the same parameters
    check_for_matching_parameters(pkg_bundle_dir, pkg_name)

    # copy the csv's into a new data package directory
    flatten_data_packages_csvs(pkg_bundle_dir,
                               pkg_name=pkg_name)
    # generate a flattened dp metadata descriptor
    pkg_descriptor = flatten_data_package_metadata(pkg_bundle_dir,
                                                   pkg_name=pkg_name)
    # using the pkg_descriptor, validate and save the data package metadata
    report = pudl.load.metadata.validate_save_pkg(
        pkg_descriptor,
        pkg_dir=pathlib.Path(pkg_bundle_dir, pkg_name))
    return(report)