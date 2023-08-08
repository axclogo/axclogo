#!/bin/bash

ls

count=1

echo "=========【START】========="
git config --global user.email "axclogo@163.com.com"
git config --global user.name "axclogo"
  
echo '正在切换到远端分支'
git checkout main
git branch
echo '同步远端分支'
git config pull.rebase true
git pull
echo "正在添加变更"
rand_str=$RANDOM
echo $rand_str >> ./assets/random.md
echo "检查文件状态"
git status -s
# 如果有文件变动，则提交掉
if [ -n "$(git status --porcelain)" ]; then
    echo "检测到变更，正在提交变更文件"
    git add -A
    git commit -m '【Auto】 - Git Refresh'
    echo '同步远端分支'
    git config pull.rebase true
    git pull
    echo '推送远端分支'
    git push
fi
echo '同步远端分支'
git config pull.rebase true
git pull
echo '推送远端分支'
git push
echo '=========【END】========='
