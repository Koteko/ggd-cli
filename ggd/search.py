# -------------------------------------------------------------------------------------------------------------
## Import Statements
# -------------------------------------------------------------------------------------------------------------
from __future__ import print_function

import sys

from .utils import get_builds, get_ggd_channels, get_species

SPECIES_LIST = sorted(get_species(update_files=False))
GENOME_BUILDS = sorted(get_builds("*"))
CHANNEL_LIST = [x.encode("ascii") for x in get_ggd_channels()]

# -------------------------------------------------------------------------------------------------------------
## Argument Parser
# -------------------------------------------------------------------------------------------------------------
def add_search(p):

    c = p.add_parser(
        "search",
        help="Search for a ggd data package",
        description="Search for available ggd data packages. Results are filtered by match score from high to low. (Only 5 results will be reported unless the -dn flag is changed)",
    )
    c.add_argument(
        "search_term",
        nargs="+",
        help="**Required** The term(s) to search for. Multiple terms can be used. Example: 'ggd search reference genome'",
    )
    c.add_argument(
        "-g",
        "--genome-build",
        default=[],
        action="append",
        choices=[str(x) for x in GENOME_BUILDS],
        help="(Optional) Filter results by the genome build of the desired recipe",
    )
    c.add_argument(
        "-s",
        "--species",
        default=[],
        action="append",
        help="(Optional) Filter results by the species for the desired recipe",
        choices=[str(x) for x in SPECIES_LIST],
    )
    c.add_argument(
        "-dn",
        "--display-number",
        default=5,
        help="(Optional) The number of search results to display. (Default = 5)",
    )
    c.add_argument(
        "-m",
        "--match-score",
        default="75",
        help="(Optional) A score between 0 and 100 to use to filter the results by. (Default = 75). The lower the number the more results will be output",
    )
    c.add_argument(
        "-c",
        "--channel",
        help="(Optional) The ggd channel to search. (Default = genomics)",
        choices=[x.decode("ascii") for x in CHANNEL_LIST],
        default="genomics",
    )
    c.set_defaults(func=search)


# -------------------------------------------------------------------------------------------------------------
## Functions/Methods
# -------------------------------------------------------------------------------------------------------------


def load_json(jfile):
    """Method to load a json file into a dictionary

    load_json
    =========
    Method to load a json file 

    Parameters:
    ---------
    1) jfile: The path to the json file

    Returns:
    1) A dictionary of a json object 
    """
    import json

    with open(jfile) as jsonFile:
        return json.load(jsonFile)


def load_json_from_url(json_url):
    """Method to load a json file from a url

    load_json_from_url
    ==================
    Method to load a json file  from a url. Uses the requests module 
     to get the json file from the url.
   
    Parameters:
    ---------
    1) json_url: The url to the json path
   
    Returns:
    ++++++++
    1) A dictionary of a json object 
    """
    import json
    import requests
    import traceback

    try:
        return requests.get(json_url).json()
    except ValueError as e:
        sys.stderr.write("\n:ggd:search: !!ERROR!! in loading json file from url")
        sys.stderr.write("\n\t Invalid URL: %s" % json_url)
        sys.stderr.write(str(e))
        sys.stderr.write(traceback.format_exc())
        sys.exit(1)


def search_packages(json_dict, search_terms, score_cutoff=50):
    """Method to search for ggd packages in the ggd channeldata.json metadata file based on user provided search terms

    search_packages
    ===============
    Method to search for ggd packages/recipes 
     contaning specific search terms 

     NOTE: Both the package name and the package keywords are searched

    Parameters:
    ---------
    1) json_dict: A json file loaded into a dictionary. (The file to search)
                  the load_json_from_url() method creates the dictionary 
    2) search_terms: A list of terms representing package names or keywords to search for
    3) score_cutoff: A number betwnee 0 and 100 that represent which matches to return
                        (Default = 50)

    Returns:
    ++++++++
    1) A list of pkg names who's either name or keyword match score reached the score cutoff
    """
    from fuzzywuzzy import fuzz
    from fuzzywuzzy import process

    pkg_score = {}
    for term in search_terms:
        for pkg in json_dict["packages"].keys():
            ## Get match score between name and term
            score = fuzz.partial_ratio(term.lower(), pkg.lower())
            ## Get a list of match score for the keywrods
            additional_scores = process.extract(
                term, json_dict["packages"][pkg]["keywords"]
            )
            ## Get the max score from all scores found
            max_score = max([x[1] for x in additional_scores] + [score])

            ## Set max score in dict
            if pkg in pkg_score:
                pkg_score[pkg] = max(pkg_score[pkg], max_score)
            else:
                pkg_score[pkg] = max_score

    ## Get a final list of pkg names
    temp_list = sorted(
        [
            [pkg, int(max_score)]
            for pkg, max_score in pkg_score.items()
            if max_score >= score_cutoff
        ],
        key=lambda x: x[1],
        reverse=True,
    )
    final_list = [pkg_list[0] for pkg_list in temp_list]

    return final_list


def check_installed(ggd_recipe, ggd_jdict):
    """Method to check if the recipe has already been installed and is in the conda ggd storage path. 
        
    check_if_installed
    ==================
    This method is used to check if the ggd package has been installed and is located in the ggd storage path.
    """
    import glob
    import os
    from .utils import conda_root

    species = ggd_jdict["packages"][ggd_recipe]["identifiers"]["species"]
    build = ggd_jdict["packages"][ggd_recipe]["identifiers"]["genome-build"]
    version = ggd_jdict["packages"][ggd_recipe]["version"]

    CONDA_ROOT = conda_root()
    path = os.path.join(CONDA_ROOT, "share", "ggd", species, build, ggd_recipe, version)
    recipe_exists = glob.glob(path)
    if recipe_exists:
        return (True, path)

    else:
        return (False, None)


def filter_by_identifiers(iden_keys, json_dict, filter_terms):
    """Method to filter a dictionary by an identifier field for the certain package.

    filter_by_identifiers
    =====================
    A method used to filter the list of data packages by information in the 
     identifiers field in the channeldata.json file

    Parameters:
    ----------
    1) iden_keys: A list of he identifiers keys. Example = ["species","genome-build"] 
    2) json_dict: The json dictionary craeted from laod_json()
    3) filter_terms: A list of the term(s) to filter by. Example: ["Homo_sapiens","hg19"]

    NOTE: List order of iden_keys should match list order of filter_terms

    Returns:
    ++++++++
    1) Updated/filtered json_dict
    """
    import copy

    key_count = len(json_dict["packages"].keys())
    keys = json_dict["packages"].keys()

    keys_to_keep = set()
    if len(iden_keys) > 0 and len(iden_keys) == len(filter_terms):
        for key in keys:
            for i, iden_key in enumerate(iden_keys):
                if iden_key in json_dict["packages"][key]["identifiers"]:
                    if len(filter_terms[i]) == 0:
                        continue
                    if (
                        filter_terms[i]
                        in json_dict["packages"][key]["identifiers"][iden_key]
                    ):
                        keys_to_keep.add(key)

    new_json_dict = copy.deepcopy(json_dict)
    ## Remove packages
    if len(keys_to_keep) > 0:
        for key in keys:
            if key not in keys_to_keep:
                del new_json_dict["packages"][key]

    if len(new_json_dict["packages"].keys()) == key_count:
        ## If unable to return a filtered set return the original match list
        print(
            "\n:ggd:search: WARNING: Unable to filter packages using: '%s'"
            % ", ".join(filter_terms)
        )
        print("\tThe un-filtered list will be used\n")

    return new_json_dict


def print_summary(search_terms, json_dict, match_list, installed_pkgs, installed_paths):
    """ Method to print the summary/results of the search

    print_summary
    ============
    Method used to print out the final set of searched packages

    Parameters:
    ---------
    1) search_terms: The search terms from the user
    2) json_dict: The json dictionary from the load_json() method
    3) match_list: The filtered and final set of searched recipes
    4) isntalled_pkgs: A set of pkg names that are installed
    5) installed_paths: A dictionary with keys = pkg names, values = installed paths

    Returns:
    +++++++
    1) True if print summary printed out successfully
    """

    dash = "     " + "-" * 100

    if len(match_list) < 1:
        print(
            "\n:ggd:search: No results for %s. Update your search term(s) and try again"
            % ", ".join(search_terms)
        )
        sys.exit()
    print("\n", dash)
    for pkg in match_list:
        results = []
        if pkg in json_dict["packages"]:
            # results.append("\n\t{} {}\n".format(("\033[1m" + "GGD Package:" + "\033[0m"), pkg))
            results.append(
                "\n\t{}\n\t{}".format(("\033[1m" + pkg + "\033[0m"), "=" * len(pkg))
            )
            if (
                "summary" in json_dict["packages"][pkg]
                and json_dict["packages"][pkg]["summary"]
            ):
                results.append(
                    "\t{} {}".format(
                        ("\033[1m" + "Summary:" + "\033[0m"),
                        json_dict["packages"][pkg]["summary"],
                    )
                )
            if (
                "identifiers" in json_dict["packages"][pkg]
                and json_dict["packages"][pkg]["identifiers"]
            ):
                results.append(
                    "\t{} {}".format(
                        ("\033[1m" + "Species:" + "\033[0m"),
                        json_dict["packages"][pkg]["identifiers"]["species"],
                    )
                )
                results.append(
                    "\t{} {}".format(
                        ("\033[1m" + "Genome Build:" + "\033[0m"),
                        json_dict["packages"][pkg]["identifiers"]["genome-build"],
                    )
                )
            if (
                "keywords" in json_dict["packages"][pkg]
                and json_dict["packages"][pkg]["keywords"]
            ):
                results.append(
                    "\t{} {}".format(
                        ("\033[1m" + "Keywords:" + "\033[0m"),
                        ", ".join(json_dict["packages"][pkg]["keywords"]),
                    )
                )
            if (
                "tags" in json_dict["packages"][pkg]
                and json_dict["packages"][pkg]["tags"]
            ):
                if "cache" in json_dict["packages"][pkg]["tags"]:
                    results.append(
                        "\t{} {}".format(
                            ("\033[1m" + "Cached:" + "\033[0m"),
                            json_dict["packages"][pkg]["tags"]["cached"],
                        )
                    )
                if "data-provider" in json_dict["packages"][pkg]["tags"]:
                    results.append(
                        "\t{} {}".format(
                            ("\033[1m" + "Data Provider" + "\033[0m"),
                            json_dict["packages"][pkg]["tags"]["data-provider"],
                        )
                    )
                if "data-version" in json_dict["packages"][pkg]["tags"]:
                    results.append(
                        "\t{} {}".format(
                            ("\033[1m" + "Data Version:" + "\033[0m"),
                            json_dict["packages"][pkg]["tags"]["data-version"],
                        )
                    )
                if "file-type" in json_dict["packages"][pkg]["tags"]:
                    results.append(
                        "\t{} {}".format(
                            ("\033[1m" + "File type(s):" + "\033[0m"),
                            ", ".join(json_dict["packages"][pkg]["tags"]["file-type"]),
                        )
                    )
                if "genomic-coordinate-base" in json_dict["packages"][pkg]["tags"]:
                    results.append(
                        "\t{} {}".format(
                            ("\033[1m" + "Data file coordinate base:" + "\033[0m"),
                            json_dict["packages"][pkg]["tags"][
                                "genomic-coordinate-base"
                            ],
                        )
                    )
                if "final-files" in json_dict["packages"][pkg]["tags"]:
                    results.append(
                        "\t{} {}".format(
                            ("\033[1m" + "Included Data Files:" + "\033[0m"),
                            "\n\t\t"
                            + "\n\t\t".join(
                                json_dict["packages"][pkg]["tags"]["final-files"]
                            ),
                        )
                    )

            if pkg in installed_pkgs:  ## IF installed
                results.append(
                    "\n\tThis pacakge is already installed on your system.\n\t  You can find the installed data files here:  %s"
                    % installed_paths[pkg]
                )
            else:
                results.append("\n\tTo install run:\n\t\tggd install %s" % pkg)
        print("\n\n".join(results))
        print("\n", dash)

    return True


def search(parser, args):
    """Main method for ggd search. 

    search
    =====
    Main method for running a recipe/package search

    Parameters:
    ----------
    1) parser  
    2) args
    """
    from .utils import get_channeldata_url, get_builds

    ## load the channeldata.json file
    j_dict = load_json_from_url(get_channeldata_url(args.channel))

    ## identify if search_terms have any species or genome build in them
    species_lower = {x.lower(): x for x in SPECIES_LIST}
    gb_lower = {x.lower(): x for x in GENOME_BUILDS}
    filtered_search_terms = []
    for term in args.search_term:
        if term.lower() in species_lower.keys():
            if species_lower[term.lower()] not in args.species:
                args.species.append(species_lower[term.lower()])
        elif term.lower() in gb_lower.keys():
            if gb_lower[term.lower()] not in args.genome_build:
                args.genome_build.append(gb_lower[term.lower()])
        else:
            ## Only use search terms that are not used to filter the results by identifiers
            filtered_search_terms.append(term)

    ## genome_build takes precedence over species (If genome build provided, species is implied)
    final_species_list = args.species
    for species in args.species:
        build = get_builds(species)
        if [x for x in build if x in args.genome_build]:
            final_species_list.remove(species)
    args.species = final_species_list

    ## Filter the json dict by species or genome build if applicable
    if args.genome_build or args.species:
        j_dict = filter_by_identifiers(
            ["species"] * len(args.species) + ["genome-build"] * len(args.genome_build),
            j_dict,
            args.species + args.genome_build,
        )

    ## Search pkg names and keywords
    match_results = search_packages(
        j_dict, filtered_search_terms, int(args.match_score)
    )

    ## Get installed paths
    installed_dict = {}
    installed_set = set()
    for pkg in match_results:
        isinstalled, path = check_installed(pkg, j_dict)
        if isinstalled:
            installed_dict[pkg] = path
            installed_set.add(pkg)

    ## Print search results
    match_result_num = str(len(match_results))
    if int(match_result_num) >= int(args.display_number):
        subset_match_results = match_results[0 : int(args.display_number)]
    else:
        subset_match_results = match_results

    ## Print search results to STDOUT
    printed = print_summary(
        args.search_term, j_dict, subset_match_results, installed_set, installed_dict
    )

    ## Add a comment if a subset of search results are provided
    if int(match_result_num) > int(args.display_number):
        print(
            "\n\n:ggd:search: NOTE  Only showing results for top {d} of {m} matches.".format(
                d=str(args.display_number), m=match_result_num
            )
        )

        print(
            ":ggd:search: To display all matches append your search command with '-dn {m}'".format(
                m=match_result_num
            )
        )
        print(
            "\n\t ggd search {t} -dn {m}\n".format(
                t=" ".join(args.search_term), m=match_result_num
            )
        )

    ## Return result of print_summary
    return printed
