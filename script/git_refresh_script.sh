#!/bin/sh -
# compressed by gzexe
lines=19
prog=`/usr/bin/basename "$0"`
tmp=`/usr/bin/mktemp -d /tmp/gzexeXXXXXXXXXX` || {
/bin/echo "$prog: cannot create tmp dir"; exit 1
}
trap '/bin/rm -rf "$tmp"' 0
if /usr/bin/tail +$lines "$0" |
    /usr/bin/gzip -dc > "$tmp/$prog" 2> /dev/null; then
/bin/chmod u+x "$tmp/$prog"
"$tmp/$prog" ${1+"$@"}
ret=$?
else
/bin/echo "$prog: cannot decompress $0"
ret=1
fi
exit $ret
��
�d git_refresh_script.sh �Q�J�@��W\c ��е�hq�BԵ����D2W��V�ZA�������.D�~�f�+��iJE��Ms��'�mW���B�0A�!�'�{�W���Ck�Z���>�"�T/p�"�6,���a+g�jT�g�&�l������֌������ �Jz�Q%f�ߡ!D��:6J2�amjZզ_�M��BL���q�U�l�(�4�_�[7Qe�m�HhΦ`Xؘ�
�n�m$��au�Q�ʮN��yn�����X�1���~�;W����)Z=�6v�ޭ��zs�P_5u";9S��L����;f��8d��^~{�k�ޱ�$���i@ E�F���$6��1O7͞�����?)$�P��)��B�\�_"����GX�-_Hro���,���H�w�b�;�A"�  