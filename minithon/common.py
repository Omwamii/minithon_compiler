import re


class CommonException(Exception):
    def __init__(
        self, msg: str, source_code: str, position: int, print_token=True, is_syntax_err=False
    ) -> None:
        line_start_pos = (
            source_code.rfind("\n", 0, position) + 1 if position != 0 else 0
        )
        line_end_pos = source_code.find("\n", position)
        if line_end_pos == -1:
            # In instances where the unrecognized string is in the last line, this would find would
            # return -1, which isn't effective in finding the next newline to pinpoint the error source
            line_end_pos = len(source_code) # go to end of the source string

        line = source_code[line_start_pos:line_end_pos]

        token_line_pos = max(0, min(position - line_start_pos, len(line)))
        tail = line[token_line_pos:]
        token = ""
        highlight_pos = token_line_pos
        highlight_len = 1
        match = re.search(r"\S+", tail)
        if match is not None:
            token = match.group(0)
            highlight_pos = token_line_pos + match.start()
            highlight_len = max(1, len(token))

        highlighter = (" " * highlight_pos) + ("^" * highlight_len)
        err = f"{line}\n\033[32m{highlighter}\033[0m"
        final_err = f":\n{err}"
        line_number = source_code[:position].count("\n") + 1
        token_str = f'\033[32m"{token}"\033[0m ' if print_token and token else ""
        
        if is_syntax_err:
            super().__init__(
                f"\033[31m{msg} \033[31mat line {line_number}{f', found \033[0m{token_str}' if len(token_str) else ''} \033[0m{final_err}"
            )
        else:
            super().__init__(
                f"\033[31m{msg} \033[0m{token_str}\033[31mat line {line_number}\033[0m{final_err}"
            )
