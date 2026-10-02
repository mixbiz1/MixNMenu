"""Shared BOX/KG projection rules for the sales UI and sales API."""
from decimal import Decimal


def project_lot_stock(available_boxes, available_weight, issued_boxes,
                      issued_weight, restored_boxes=0, restored_weight=0):
    """Return stock after applying independent BOX and KG movements.

    ``restored_*`` is used by the edit screen to put the selected sale back
    before subtracting the values currently entered in the grid.
    """
    boxes = int(available_boxes) + int(restored_boxes) - int(issued_boxes)
    weight = (Decimal(str(available_weight)) + Decimal(str(restored_weight))
              - Decimal(str(issued_weight)))
    return boxes, weight
