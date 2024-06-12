#!/bin/bash

mdbook build "$@"
MDBOOK_OUTPUT__HTML__THEME=../theme MDBOOK_OUTPUT__HTML__ADDITIONAL_CSS='["../theme/nomicon.css", "../theme/language-picker.css"]' mdbook build en -d ../book/en