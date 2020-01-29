# py_readpaper

## Install

In MacOS, you need to install exiftool first. 

```{bash}
$ brew install exiftool
$ pip install -e .
```

## Usage

```{python}
import py_readpaper
flist = glob.glob('198*.pdf')
idx = 1
p = py_readpaper.Paper(flist[idx], debug=False)
print(p)
```
