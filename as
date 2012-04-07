./langc.py g --full $1 > $1.ll
clang -o ${1%.lng} $1.ll
rm $1.ll
