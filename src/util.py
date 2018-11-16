def camel(snake):
    "convert a snake_case string to camelCase"
    return snake[0].lower() + snake.title().replace("_", "")[1:]


def commonprefix(m):
    if not m:
        return ""
    s1, s2 = min(m), max(m)
    for i, c in enumerate(s1):
        if c != s2[i]:
            return s1[:i]
    return s1
