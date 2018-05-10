_taw_completion() {
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                   COMP_CWORD=$COMP_CWORD \
                   _TAW_COMPLETE=complete $1 ) )
    return 0
}

complete -F _taw_completion -o default taw;
