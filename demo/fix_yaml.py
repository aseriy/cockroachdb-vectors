import yaml

class Dumper(yaml.SafeDumper):
    pass

def str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

Dumper.add_representer(str, str_presenter)

def clean(x):
    if isinstance(x, dict):
        return {
            k: clean(v)
            for k, v in x.items()
            if k not in ("ddl", "columns")
        }
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x

with open("domains.yaml", "r") as f:
    data = yaml.safe_load(f)

data = clean(data)

with open("domains.yaml.new", "w") as f:
    yaml.dump(data, f, Dumper=Dumper, sort_keys=False, width=1000)