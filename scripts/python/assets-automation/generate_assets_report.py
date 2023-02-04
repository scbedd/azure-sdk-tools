import os, argparse, glob, json, datetime, re

from subprocess import run
from typing import List, Dict, Any

import yaml  # pyyaml
from packaging import version  # from packaging
from ci_tools.functions import (
    discover_targeted_packages,
)  # azure-sdk-tools from azure-sdk-for-python

generated_folder = os.path.abspath(os.path.join(os.path.abspath(__file__), "..", "generated"))

TABLE_HEADER: str = """| Package | Using Proxy | External Recordings |
|---|---|---|
"""

TABLE_LAYER: str = """|{}|{}|{}|
"""

YES = "✅"
NO = "❌"

DOCUMENT: str = """
<table>
<tr>
<td>

{}

</td>
<td>

{}

</td>
</tr>
</table>

"""

TABLE_HEIGHT: int = 10
BATCH_SIZE = TABLE_HEIGHT * 2


class ScanResult:
    def __init__(self, language: str):
        self.language = language
        self.packages: List[str] = []
        self.packages_using_proxy: List[str] = []
        self.packages_using_external: List[str] = []


def get_repo(language: str) -> str:
    where = f"https://github.com/azure/azure-sdk-for-{language.lower()}"
    target_folder = os.path.join(generated_folder, language)
    print(f"Cloning repo for {language} from {where}", end="...")

    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

        command = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            "main",
            where,
            target_folder,
        ]
        run(command, cwd=generated_folder)
    print(YES)

    return target_folder


def evaluate_python_package(package_path: str) -> int:
    service_dir, _ = os.path.split(package_path)
    recordings_path = os.path.join(package_path, "tests", "recordings", "*.json")
    assets_json = os.path.join(package_path, "assets.json")
    ci_yml = os.path.join(service_dir, "ci.yml")
    result = 0

    if os.path.exists(ci_yml):
        with open(ci_yml, "r") as file:
            ci_config = yaml.safe_load(file)

            # there is no reason to even do further evaluation if the TestProxy parameter isn't set. CI won't use it if it's not.
            parameters = ci_config["extends"]["parameters"]
            if "TestProxy" in parameters and parameters["TestProxy"] == True:
                # if there is an assets.json present at root, we are done. it's transitioned.
                if os.path.exists(assets_json):
                    return 2

                # otherwise, we have to check the recordings for yml (vcrpy) or json (test-proxy)
                test_proxy_files = glob.glob(recordings_path)
                if test_proxy_files:
                    return 1
    return result


def generate_python_report() -> ScanResult:
    language = "Python"
    repo = get_repo(language)
    print(f"Evaluating repo for {language} @ {repo}", end="...")

    result = ScanResult(language)

    results = discover_targeted_packages("azure*", repo)

    result.packages = sorted([os.path.basename(pkg) for pkg in results])

    for pkg in results:
        evaluation = evaluate_python_package(pkg)
        if evaluation == 1:
            result.packages_using_proxy.append(os.path.basename(pkg))
        elif evaluation == 2:
            result.packages_using_proxy.append(os.path.basename(pkg))
            result.packages_using_external.append(os.path.basename(pkg))

    print("done.")
    return result


def evaluate_go_package(package_path: str) -> int:
    evaluation = 0
    possible_recordings_dir = os.path.join(package_path, "testdata", "recordings")
    possible_assets = os.path.join(package_path, "assets.json")

    if os.path.exists(possible_recordings_dir):
        evaluation = 1

    if os.path.exists(possible_assets):
        evaluation = 2

    return evaluation


# evaluate by finding a testdata/recordings
def generate_go_report() -> ScanResult:
    language = "Go"

    repo_root = get_repo(language)

    print(f"Evaluating repo for {language} @ {repo_root}", end="...")

    result = ScanResult(language)
    sdk_path = os.path.join(repo_root, "sdk")

    exclusions = [os.path.join("testdata", "perf", "go.mod"), "template", "samples"]

    packages = glob.glob(os.path.join(repo_root, "sdk", "**", "go.mod"), recursive=True)
    packages = [os.path.dirname(pkg) for pkg in packages if not any([x in pkg for x in exclusions])]

    result.packages = [pkg.replace(sdk_path + os.sep, "") for pkg in packages]

    for pkg in packages:
        evaluation = evaluate_go_package(pkg)

        if evaluation == 1:
            result.packages_using_proxy.append(pkg.replace(sdk_path + os.sep, ""))
        elif evaluation == 2:
            result.packages_using_proxy.append(pkg.replace(sdk_path + os.sep, ""))
            result.packages_using_external.append(pkg.replace(sdk_path + os.sep, ""))

    print("done.")

    return result


def evaluate_net_package(solution_path: str) -> int:
    evaluation = 0

    # track 2 indicators within a given sln
    # Project("{9A19103F-16F7-4668-BE54-9A1E7A4F7556}") = "Azure.Core", "..\core\Azure.Core\src\Azure.Core.csproj", "{C04D725B-B025-4B41-BAF0-BEE3F8D087AB}"
    # Project("") = "Azure.Core.TestFramework", "..\..\core\Azure.Core.TestFramework\src\Azure.Core.TestFramework.csproj", "{EE26B4BC-37DB-4C5C-8519-4B8081012AF8}"
    core_pattern = r"^\s*Project\(\"[\d\S\-\_]*?\"\)\ \=\ \"Azure\.Core\""
    framework_pattern = r"^\s*Project\(\"[\d\S\-\_]*?\"\)\ \=\ \"Azure\.Core\.TestFramework\""

    with open(solution_path, "r") as f:
        content = f.read()

    core_present = re.findall(core_pattern, content, re.MULTILINE)
    core_test_present = re.findall(framework_pattern, content, re.MULTILINE)

    if core_present or core_test_present:
        evaluation = 1

    return evaluation


def net_trim_path(solution_path: str) -> str:
    return os.path.splitext(os.path.basename(solution_path))[0]


def generate_net_report() -> ScanResult:
    language = "net"
    result = ScanResult("." + language.upper())
    repo = get_repo(language)

    print(f"Evaluating repo for {language} @ {repo}", end="...")

    globby_glob = os.path.join(repo, "sdk", "**", "*.sln")
    all_solutions = set([sln for sln in glob.glob(globby_glob, recursive=True)])

    result.packages = sorted([net_trim_path(sln) for sln in all_solutions])

    for solution in all_solutions:
        evaluation = evaluate_net_package(solution)

        if evaluation == 1:
            result.packages_using_proxy.append(net_trim_path(solution))
        elif evaluation == 2:
            result.packages_using_proxy.append(net_trim_path(solution))
            result.packages_using_external.append(net_trim_path(solution))

    print("done.")

    return result


def evaluate_cpp_package(package_path: str) -> int:
    evaluation = 0

    possible_assets_json = os.path.join(package_path, "..", "assets.json")

    if False:
        evaluation = 1

    if os.path.exists(possible_assets_json):
        evaluation = 2

    return evaluation


def generate_cpp_report() -> ScanResult:
    language = "CPP"
    result = ScanResult(language)
    repo_root = get_repo(language)

    print(f"Evaluating repo for {language} @ {repo_root}", end="...")

    exclusions = [os.path.join("vcpkg", "vcpkg.json"), "template"]

    packages = glob.glob(os.path.join(repo_root, "sdk", "**", "vcpkg.json"), recursive=True)
    packages = [os.path.dirname(pkg) for pkg in packages if not any([x in pkg for x in exclusions])]

    result.packages = sorted([os.path.basename(pkg) for pkg in packages])
    for pkg in packages:
        evaluation = evaluate_cpp_package(pkg)

        if evaluation == 1:
            result.packages_using_proxy.append(os.path.basename(pkg))
        elif evaluation == 2:
            result.packages_using_proxy.append(os.path.basename(pkg))
            result.packages_using_external.append(os.path.basename(pkg))

    print("done.")
    return result


def evaluate_js_package(package_path: str) -> int:
    with open(package_path, "r", encoding="utf-8") as f:
        package_json = json.load(f)

    assets_json = os.path.join(os.path.dirname(package_path), "assets.json")
    if os.path.exists(assets_json):
        return 2

    if "devDependencies" in package_json:
        if "@azure-tools/test-recorder" in package_json["devDependencies"]:
            version_spec = package_json["devDependencies"]["@azure-tools/test-recorder"]
            if version_spec[0] == "^":
                version_spec = version_spec[1:]

            if version.parse(version_spec) >= version.parse("2.0.0"):
                return 1

    return 0


def e_startswith(input: str, prefixes: List[str]) -> bool:
    return any([input.startswith(fix) for fix in prefixes])


def e_endswith(input: str, postfixes: List[str]) -> bool:
    return any([input.endswith(fix) for fix in postfixes])


def e_directory_in(input_dir: str, directory_patterns: List[str]) -> bool:
    return any([input_dir in subdir for subdir in directory_patterns])


def js_package_included(package_path: str) -> bool:
    package_name = os.path.basename(os.path.dirname(package_path))

    excluded_packages = [
        "samples-react",
        "sample-react",
        "mock-hub" "abort-controller",
        "logger",
        "samples-express",
        "samples-browser" "samples-react",
        "event-hubs-track-1",
        "opentelemetry-instrumentation-azure-sdk",
        "monitor-opentelemetry-exporter",
        "service-bus-v1",
        "service-bus-v7",
        "app",
        "perf"
    ]

    excluded_package_postfixes = ["-track-1", "-common"]

    excluded_package_prefixes = ["@azure/core-"]

    # exclude any packages that have these paths in them
    excluded_directories = [
        os.path.join("sdk", "identity", "identity", "test"),
        os.path.join("sdk", "test-utils"),
        "samples",
    ]

    # only include packages with a test folder alongside
    has_test_folder = os.path.exists(os.path.join(os.path.dirname(package_path), "test"))

    # insure we don't include amqp packages (they cant convert to test-proxy)
    amqp_package = False
    with open(package_path, "r", encoding="utf-8") as f:
        package_json = json.load(f)
    if "dependencies" in package_json:
        if "@azure/core-amqp" in package_json["dependencies"]:
            amqp_package = True

    return (
        "samples" not in os.path.normpath(package_path).split(os.sep)
        and package_name not in excluded_packages
        and not e_startswith(package_name, excluded_package_prefixes)
        and not e_endswith(package_name, excluded_package_postfixes)
        and not e_directory_in(package_name, excluded_directories)
        and not amqp_package
        and has_test_folder
    )


def generate_js_report() -> ScanResult:
    language = "JS"
    repo = get_repo(language)
    print(f"Evaluating repo for {language} @ {repo}", end="...")

    target_folder = os.path.join(repo, "sdk", "**", "package.json")
    result = ScanResult(language)

    results = glob.glob(target_folder, recursive=True)

    result.packages = sorted([os.path.basename(os.path.dirname(pkg)) for pkg in results if js_package_included(pkg)])

    excluded = set(sorted([os.path.basename(os.path.dirname(pkg)) for pkg in results if not js_package_included(pkg)]))

    for pkg in results:
        evaluation = evaluate_js_package(pkg)
        if evaluation == 1:
            result.packages_using_proxy.append(os.path.basename(os.path.dirname(pkg)))
        elif evaluation == 2:
            result.packages_using_proxy.append(os.path.basename(os.path.dirname(pkg)))
            result.packages_using_external.append(os.path.basename(os.path.dirname(pkg)))

    print("done.")
    return result


def generate_detailed_table(origin: ScanResult, package_set: List[str]):
    result = TABLE_HEADER
    for package in package_set:
        transitioned = YES if package in origin.packages_using_proxy else NO
        externalized = YES if package in origin.packages_using_external else NO

        table_row = TABLE_LAYER.format(package.replace("\\", "/"), transitioned, externalized)
        result += table_row

    return result


def write_output(result: ScanResult) -> None:
    with open(result.language.lower() + ".md", "w", encoding="utf-8") as f:
        date = datetime.date.today()
        time_of_day = datetime.datetime.today().strftime("%I:%M%p")
        f.writelines(
            f"# {result.language} Transition Details as of {date}@{time_of_day} {datetime.datetime.today().astimezone().tzname()}"
        )

        if result.packages:
            # batch two sets
            batch_size = (len(result.packages) // 2) + (len(result.packages) % 2)

            table_set_1 = result.packages[0:batch_size]
            table_set_2 = result.packages[batch_size:]

            document_addition = DOCUMENT.format(
                generate_detailed_table(result, table_set_1), generate_detailed_table(result, table_set_2)
            )

            f.write(document_addition)


def write_summary(results: List[ScanResult]) -> None:
    with open("summary.md", "w", encoding="utf-8") as f:
        f.writelines(f"# Test Proxy Transition Summary - {datetime.date.today()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
      Generates a markdown report that summarizes the the status of the transition to the test-proxy and externalized assets.
      """
    )
    parser.parse_args()

    python = generate_python_report()
    write_output(python)

    js = generate_js_report()
    write_output(js)

    go = generate_go_report()
    write_output(go)

    net = generate_net_report()
    write_output(net)

    cpp = generate_cpp_report()
    write_output(cpp)

    write_summary(
        [
            python,
            js,
            go,
            net,
            cpp,
        ]
    )
