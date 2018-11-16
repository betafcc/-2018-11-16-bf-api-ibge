def camel(snake):
    "convert a snake_case string to camelCase"
    return snake[0].lower() + snake.title().replace("_", "")[1:]
