#!/usr/bin/env python3

"""
This script sets the "version" and "appVersion" of a chart before packaging it and
pushing it to an OCI repository.

The version is derived from a combination of the latest Git tag and the current SHA.
It assumes that the tags are SemVer compliant, i.e. are of the form
`<major>.<minor>.<patch>-<prerelease>`.

The appVersion is derived from the current SHA, as produced when using
`tags: type=sha,prefix=` with `docker/metadata-action`.

This means that referencing the chart at a particular SHA automatically picks up
the correct images for that version.
"""

import os
import re
import subprocess

import yaml


def cmd(command):
    """
    Execute the given command and return the output.
    """
    output = subprocess.check_output(command, text = True, stderr = subprocess.DEVNULL)
    return output.strip()


#: Regex that attempts to match a SemVer version
#: It allows the tag to maybe start with a "v"
SEMVER_REGEX = r"^v?(?P<major>[0-9]+).(?P<minor>[0-9]+).(?P<patch>[0-9]+)(-(?P<prerelease>[a-zA-Z0-9.-]+))?$"


def get_versions():
    """
    Returns a `(version, app_version)` tuple based on Git information for the current repository.
    
    `version` is SemVer compliant, based on the distance from the last tag. It is constructed such
    that the versions for a particular branch will order correctly.
    """
    # The app version is always the short SHA
    app_version = cmd(["git", "rev-parse", "--short", "HEAD"])
    # Assembling the version is more complicated
    try:
        # Start by trying to find the most recent tag
        last_tag = cmd(["git", "describe", "--tags", "--abbrev=0"])
    except subprocess.CalledProcessError:
        # If there are no tags, then set the parts in such a way that when we increment the patch version we get 0.1.0
        major_vn = 0
        minor_vn = 1
        patch_vn = -1
        prerelease_vn = None
        # Since there is no tag, just count the number of commits in the branch
        commits = int(cmd(["git", "rev-list", "--count", "HEAD"]))
    else:
        # If we found a tag, split into major/minor/patch/prerelease
        tag_bits = re.search(SEMVER_REGEX, last_tag)
        if tag_bits is None:
            raise RuntimeError(f'Tag is not a valid SemVer version - {last_tag}')
        major_vn = int(tag_bits.group('major'))
        minor_vn = int(tag_bits.group('minor'))
        patch_vn = int(tag_bits.group('patch'))
        prerelease_vn = tag_bits.group('prerelease')
        # Get the number of commits since the last tag
        commits = int(cmd(["git", "rev-list", "--count", f"{last_tag}..HEAD"]))

    if commits > 0:
        # If there are commits since the last tag and no existing prerelease part, increment the patch version
        if not prerelease_vn:
            patch_vn += 1
        # Add information to the prerelease part about the branch and number of commits
        # Get the name of the current branch
        branch_name = cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"]).lower()
        # Sanitise the branch name so it only has characters valid for a prerelease version
        branch_name = re.sub("[^a-zA-Z0-9-]+", "-", branch_name).lower().strip("-")
        prerelease_vn = '.'.join([prerelease_vn or "dev.0", branch_name, str(commits)])

    # Build the SemVer version from the parts
    version = f"{major_vn}.{minor_vn}.{patch_vn}"
    if prerelease_vn:
        version += f"-{prerelease_vn}"

    return (version, app_version)


def update_chart_versions(chart_directory, version, app_version):
    """
    Update the versions in Chart.yaml.
    """
    chart_file = os.path.join(chart_directory, "Chart.yaml")
    # Read the existing YAML
    with open(chart_file) as chart_fh:
        chart_yaml = yaml.safe_load(chart_fh)
    # Replace the versions in the YAML structure
    chart_yaml.update(version = version, appVersion = app_version)
    # Write the YAML back out to the chart file
    with open(chart_file, 'w') as chart_fh:
        yaml.safe_dump(chart_yaml, chart_fh)


def main():
    """
    Entrypoint for the script.
    """
    # First, determine the versions to use
    version, app_version = get_versions()
    print(version)
    print(app_version)
    # Update the versions in the chart
    chart_directory = os.path.realpath("./chart")
    update_chart_versions(chart_directory, version, app_version)
    # Build the chart tag - the repository should be in the environment
    chart_tag = "{}:{}".format(os.environ['CHART_REPOSITORY'], version)
    # Save the chart to the local cache
    print(["helm", "chart", "save", chart_directory, chart_tag])
    # Push the chart to the repository
    print(["helm", "chart", "push", chart_tag])


if __name__ == "__main__":
    main()
