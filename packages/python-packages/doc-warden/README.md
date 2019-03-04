# Doc Warden [![Build Status](https://dev.azure.com/azure-sdk/public/_apis/build/status/108?branchName=master)](https://dev.azure.com/azure-sdk/public/_build/latest?definitionId=108&branchName=master)

Every CI build owned by the Azure-SDK team also needs to verify that the documentation within the target repo meets a set of standards. `Doc-warden` is intended to ease the _implementation_ of these checks in CI builds.

Features:

* Enforces Readme Standards
    - Readmes present - *completed*
    - Readmes have appropriate contents - *completed*
    - Files issues for failed standards checks - *pending*
* Generates report for included observed packages - *pending*

This package is tested on Python 2.7 -> 3.8.

## Prerequisites
This package is intended to be run as part of a pipeline within Azure DevOps. As such, [Python](https://www.python.org/downloads/) must be installed prior to attempting to install or use `Doc-Warden.` While `pip` comes pre-installed on most modern Python installs, if `pip` is an unrecognized command when attempting to install `warden`, run the following command **after** your Python installation is complete.

In addition, `warden` is distributed using `setuptools` and `wheel`, so those packages should also be present prior to install. 

```
/:> python -m ensurepip
/:> pip install setuptools wheel
```

## Usage

Right now, `warden` has a single command.  `scan`, which by default looks for a target `.docsettings.yml` file within the target repo. However, all the parameters that can be pulled from the `.docsettings` files will **override** whatever is placed within the `.docsettings` file.

Example usage:

```

<pre-step, clone target repository>
...
/:> pip install setuptools wheel
/:> sudo pip install doc-warden
/:> ward scan -d $(Build.SourcesDirectory)

```
**Notes for example above**

* Devops is a bit finicky with registering a console entry point, hence the `sudo` just on the installation. `sudo` is only required on devops machines.
* Assumption is that the `.docsettings` file is placed at the root of the repository.

To provide a different path (like `azure-sdk-for-java` does...), use: 

```

/:> ward scan -d $(Build.SourcesDirectory) -c $(Build.SourcesDirectory)/eng/.docsettings.yml

```

##### Parameter Options

`command` 
Currently supports the `scan` command. Additional commands may be supported in the future. **Required.**

`--scan-directory`
The target directory `warden` should be scanning. **Required.**

`--scan-language`
`warden` checks for packages by _convention_, so it needs to understand what language it is looking at. This must be populated either in `.docsettings file` or by parameter. **Required.**

`--config-location`
By default, `warden` looks for the `.docsettings` file in the root of the repository. However, populating this location will override this behavior and instead pull the file from the location in this parameter. **Optional.**

`--verbose-output`
Enable or disable output of an html report. Defaults to false. **Optional.**

##### Notes for Devops Usage

The `-d` argument should be `$(Build.SourcesDirectory)`. This will point `warden` at the repo that has been associated with CI.

## Methodology

### Enforcing Readme Presence 

When should we expect a readme to be present?

**Always:**

* At the root of the repo
* Associated with a `package` directory

#### .Net

A package is indicated by:
* a `*.csproj` file
    * Project file does not end with `tests.csproj`

#### Python

A package is indicated by: 

* the presence of a `setup.py` file

#### Java

A package is indicated by:

* the presence of a `pom.xml` file
    * The POM `<packaging>` value within is set to `JAR`

#### Node & JS

A package is indicated by: 

* The presence of a `package.json` file

### Enforcing Readme Content

`doc-warden` has the ability to check discovered readme files to ensure that a set of configured sections is present. How does it work? `doc-warden` will check each pattern present within `required_readme_sections` against all headers present within a target readme. If all the patterns match at least one header, the readme will pass content verification.

Other Notes:
* A `section` title is any markdown or RST that will result in a `<h1>` to `<h6>` html tag.
* `warden` will content verify any `readme.rst` or `readme.md` file found outside the `omitted_paths` in the targeted repo. 
    * Case of the readme file title is ignored.

#### Control, the `.docsettings.yml` File, and You

Special cases often need to be configured. It seems logical that there needs be a central location (per repo) to override conventional settings. To that end, a new `.docsettings.yml` file will be added to each repo. 

```
<repo-root>
│   README.md
│   .docsettings.yml
│
└───.azure-pipelines
│   │   <build def>
│   
└───<other files and folders>
```

The presence of this file allows each repository to customize how enforcement takes place within their repo.

**Example DocSettings File for Java Repo**

```
omitted_paths:
  - archive/*
language: java
root_check_enabled: True
required_readme_sections:
  - "(Client Library for Azure .*|Microsoft Azure SDK for .*)"
  - Getting Started
```

The above configuration tells `warden`...

- The language within the repo is `java`
- To ensure that a `README.md` is present at the root of the repository.
- To omit any paths under `archive/` from the readme checks.

Possible values for `language` right now are `['net', 'java', 'js', 'python']`. Greater than one target language is not currently supported.

##### `required_readme_sections` Configuration
This section instructs `warden` to verify that there is at least one matching section title for each provided `section` pattern in any discovered readme. Regex is fully supported.

The two items listed from the example `.docsettings` file will:
- Match a header matched by a simple regex expression
- Match a header exactly titled "Getting Started"

Note that the regex is surrounded by quotation marks where the regex will break `yml` parsing of the configuration file.

## Provide Feedback

If you encounter any bugs or have suggestions, please file an issue [here](https://github.com/Azure/azure-sdk-tools/issues) and assign to `scbedd`.
