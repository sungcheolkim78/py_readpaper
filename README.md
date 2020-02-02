# py_readpaper

논문을 컴퓨터가 읽고 그 내용을 파악하여 서지 정보를 찾아주고 텍스트를 요약해 줄 수 있다면, 연구를 하는데 여러 시간을 아낄 수 있을 것이다. 이 라이브러리는 이러한 목표를 이루기 위해 가장 기본이 되는 논문의 텍스트, 메타정보 분석하는 일에 관한 함수들을 가지고 있다. 여기서 중요한 점 중에 하나는 각각의 pdf 파일들이 최대한 많은 서지 정보를 갖도록 하는 것이다. exif tag를 이용해서 논문의 저자, 년도, 저널, 제목등을 저장하도록 하고 또한 파일에 해당하는 숨겨진 파일을 bibtex 형식으로 저장하여서 이중의 메타정보 보관 시스템을 만들었다. 

## Versions

- 2019/04/11 - initial version
- 2019/04/14 - redesign concept and layer of functions
- 2019/05/06 - optimization

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

### meta information Management

우선 파일명에서 `year`, `author_s`, `journal`의 정보를 알아낼 수 있다. (이는 수동으로 해야 한다.) `pdftotext`나 `pdfminer`를 사용해서 pdf에서 텍스트를 추출할 수 있는데, pdf 파일 자체가 글을 적는 용도가 아니라 그림을 저장하는 용도에 가까운 포맷이라 거기서 따로 서지정보를 알아내기가 쉽지 않다.

- [ ] pdf 파일로부터 논문의 title을 뽑아내자. 자동으로 모든 것을 할 수 없다면 몇가지 옵션으로 추려내고 선택을 사용자에게 맡기자.
- [ ] pdf 파일로부터 keyword를 자동으로 생성하자. gensim을 통해서 자연어 처리 알고리즘으로 abstract나 모든 본문에서 keyword를 생성할 수 있다.
- [ ] 기존 정보 (year, author, journal)을 본문을 통해 확인할 수 있다.
- [ ] pdf 파일을 metadata를 업데이트 한다.
