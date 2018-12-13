# epa-metvi
Curating and analyzing instances of the EPA or regulation/regulators "strangling" "the economy"

Currently this repository is in a messy state. You will have to clone `iatv` and `metacorps` after
cloning this repository. Then `touch metacorps/__init__.py` to have access from the root epa-metvi directory.
Edit `metacorps/projects/common/export_project.py` to change line 16 from

```python
from app.models import Project, IatvDocument
```

to

```python
from metacorps.app.models import Project, IatvDocument
```

iatv repo: https://github.com/mt-digital/iatv.git

metacorps repo: https://github.com/mt-digital/metacorps.git
