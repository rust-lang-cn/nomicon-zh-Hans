#!/bin/bash

mdbook build "$@"
MDBOOK_OUTPUT__HTML__THEME=../theme MDBOOK_OUTPUT__HTML__ADDITIONAL_CSS='["../theme/nomicon.css", "../theme/language-picker.css"]' MDBOOK_OUTPUT__HTML__SEARCH__USE_BOOLEAN_AND=true mdbook build en -d ../book/en