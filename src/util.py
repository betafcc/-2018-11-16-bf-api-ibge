from functools import reduce

import oyaml
from box import Box
import apistar
import apistar.validators


def call(f):
    return f()


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


def deep_merge(*dicts):
    return reduce(_deep_merge, dicts)


def _deep_merge(a, b):
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return b

    return {
        **a,
        **b,
        **{k: _deep_merge(a[k], b[k]) for k in set(a).intersection(set(b))},
    }


def spec_errors(spec):
    try:
        apistar.validate(spec, format='swagger')
        return []
    except apistar.validators.ValidationError as error:
        return error.args[0]


class yaml(Box):
    @classmethod
    def load(cls, path):
        with open(path) as fp:
            return cls(oyaml.load(fp))

    def dump(self, path=None, **kwargs):
        result = oyaml.dump(
            self.to_dict(), allow_unicode=True, default_flow_style=False, **kwargs
        )
        if not path:
            return result
        try:
            with open(path, "w") as fp:
                fp.write(result)
        except TypeError:
            path.write(result)

    def __repr__(self):
        return self.dump()

    def print(self):
        print(self)
