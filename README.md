# jasmin-cloud

API for administration of projects in the JASMIN Cloud.


## Documentation

Documentation for `jasmin-cloud` is available on the
[Github Pages site for the cedadev organisation](http://cedadev.github.io/jasmin-cloud/).

### Building the documentation

In order for [Sphinx autodoc](http://www.sphinx-doc.org/en/stable/ext/autodoc.html)
to work correctly, [Sphinx](http://www.sphinx-doc.org/) must run in a context where
all the dependencies are installed. The easiest way to do this is with a
[virtual environment](https://docs.python.org/3/library/venv.html):

```#sh
$ python3 -m venv venv-jasmin-cloud-sphinx
$ source venv-jasmin-cloud-sphinx/bin/activate
$ pip install sphinx sphinx_rtd_theme
$ pip install -r requirements.txt
$ make -C docs clean html
```

You can then open `docs/build/html/index.html` in a web browser.

Make sure that the virtual environment is not committed to git, either by deleting
it after the documentation has been built or adding it `.gitignore`.

To push documentation changes to the Github Pages site, use the following command:

```
$ git subtree push --prefix docs/build/html origin gh-pages
```
