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
����d random_script.sh �SMK�@�ϯx7�����^��œ
]o�"�t��L�L�c��Z��vAD���EAD~�
��q��_p���!�i!�y�g��}g�C���fBCȦQ���ۡ`�{�s���P(.<ǿ����.��
�U�h	{1f��]�l{�J'�?}����� �'}�� �!Lyq,ZmQ_���D���S���R�ȭKS�9�^��$H)ā�t���./NSh����!Q�aD����@�˻�8�;r��@J���x��sS�zk���ds�1�Y����rO�8��r{�����q+��	�G,�F@�}��-�Z�۔�h���E}Wn6_�O��r+�� ���0ߪ��&��b̀o��;$Pa�o~�u-J�[`��A�j$��4.��*�U}��|0�\"N�X�3
,�JH�cS�H������a %7��t�Z���������M���1=75|3L�����Y  