# seiza. — Fish Syntax Highlighting, Completion Pager & Tool Palette

set -g fish_color_normal EEF1FA
set -g fish_color_command C4B5FD
set -g fish_color_keyword F2B8D4
set -g fish_color_quote 9CE0C2
set -g fish_color_redirection F5D6A8
set -g fish_color_end A6B0D0
set -g fish_color_error F28FAD
set -g fish_color_param DCE2F5
set -g fish_color_valid_path --underline
set -g fish_color_option 9CC9FF
set -g fish_color_comment 6C7699
set -g fish_color_selection --background=272F52
set -g fish_color_search_match --background=272F52
set -g fish_color_operator F5D6A8
set -g fish_color_escape F2B8D4
set -g fish_color_autosuggestion 5A6385
set -g fish_color_cancel F28FAD

set -g fish_pager_color_progress A6B0D0
set -g fish_pager_color_prefix C4B5FD --bold
set -g fish_pager_color_completion EEF1FA
set -g fish_pager_color_description A6B0D0
set -g fish_pager_color_selected_background --background=272F52
set -g fish_pager_color_selected_prefix C4B5FD --bold
set -g fish_pager_color_selected_completion F6F8FE
set -g fish_pager_color_selected_description DCE2F5

set -gx FZF_DEFAULT_OPTS " \
--color=bg+:#15192E,bg:#0D101D,spinner:#9CE0C2,hl:#C4B5FD \
--color=fg:#A6B0D0,header:#9CC9FF,info:#F5D6A8,pointer:#F2B8D4 \
--color=marker:#9CE0C2,fg+:#EEF1FA,prompt:#C4B5FD,hl+:#D6CBFE \
--color=border:#28304D,separator:#28304D,scrollbar:#28304D \
--border=rounded --height=75% --layout=reverse"

set -gx BAT_THEME "ansi"
