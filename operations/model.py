import pkgutil
import models
import importlib



def run_model_list(args):
    for mod in pkgutil.iter_modules(models.__path__):
        module = importlib.import_module(f"models.{mod.name}")
        model_label = module.embedding_label()
        print(f"{mod.name}\t{model_label}")


def run_model_desc(args):
    name = args['model']

    modules_available = [mod.name for mod in pkgutil.iter_modules(models.__path__)]
    if name not in modules_available:
        print(f"No model {args['model']} found...")
        return

    module = importlib.import_module(f"models.{name}")
    model_label = module.embedding_label()
    model_desc = module.embedding_description()
    print("-" * (len(model_label) + 4))
    print(f"| {model_label} |")
    print("-" * (len(model_label) + 4))
    print(model_desc)
    print()

