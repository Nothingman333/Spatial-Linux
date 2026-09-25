# Making a release

Notes for the maintainer; users do not need any of this.

1. Raise `__version__` in `spatiallinux/__init__.py`.
2. Add a `## v<version>` section to `CHANGELOG.md`.
3. Run **Actions → Release → Run workflow** on GitHub, or push a
   `v<version>` tag.

The [release workflow](../.github/workflows/release.yml) checks the version,
builds the `.tar.gz`, `.zip` and `SHA256SUMS`, publishes the release with
the notes from the changelog, and removes the older releases.
