Place a YOLO weights file here.

MVP default:

    models/default.pt

Later, swap to a custom GTA model without changing the analysis pipeline:

    models/gta_custom.pt

Then set:

    YOLO_MODEL_PATH=models/gta_custom.pt
