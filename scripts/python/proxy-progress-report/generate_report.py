import argparse
import os
from subprocess import run
import shutil
import glob
import pdb

from typing import List


def verify_path(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def discover_python_status(work_dir: str, repo: str) -> List[str]:
    # clone the repo into target folder
    run(["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", "."], cwd=work_dir)

    # discover all service directories
    services = glob.glob("sdk/*/ci.yml", root_dir=work_dir)

    pdb.set_trace()


def discover_net_status(work_dir: str, repo: str) -> List[str]:
    pass


def discover_go_status(work_dir: str, repo: str) -> List[str]:
    pass


def discover_js_status(work_dir: str, repo: str) -> List[str]:
    pass


REPOS = {
    "Azure/azure-sdk-for-python": discover_python_status,
    "Azure/azure-sdk-for-js": discover_js_status,
    "Azure/azure-sdk-for-net": discover_net_status,
    "Azure/azure-sdk-for-go": discover_go_status,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generates a markdown report into the targeted work directory. This report highlights the total % of transition to the test-proxy."
    )

    parser.add_argument(
        "-w",
        "--work-directory",
        dest="work_directory",
        help="The directory where work will commence. If not provided, will create a folder under the current working directory.",
        required=False,
    )

    args = parser.parse_args()
    parsed_results = REPOS.copy()

    if not args.work_directory:
        args.work_directory = os.path.join(os.getcwd(), ".work")

    # clean up the previous run
    shutil.rmtree(args.work_directory)
    os.path.mkdirs(args.work_directory)

    # walk all the repos, do the needful on each
    for repo in REPOS.keys():
        target_path = os.path.join(args.work_directory, repo.replace("/", "-"))
        verify_path(target_path)
        parsed_results[repo] = REPOS[repo](target_path, repo)

    print(parsed_results)
