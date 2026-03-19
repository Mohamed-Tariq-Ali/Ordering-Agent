# Mock product catalog - replace with your real DB/API
PRODUCT_CATALOG = {
    "choco": {
        "product_id": "PRD-001",
        "name": "Choco",
        "category": "Chocolates",
        "price": 49.99,
        "stock": 100,
        "description": "Premium dark chocolate bar",
        "unit": "bar"
    },
    "choco bar": {
        "product_id": "PRD-001",
        "name": "Choco",
        "category": "Chocolates",
        "price": 49.99,
        "stock": 100,
        "description": "Premium dark chocolate bar",
        "unit": "bar"
    },
    "milk choco": {
        "product_id": "PRD-002",
        "name": "Milk Choco",
        "category": "Chocolates",
        "price": 39.99,
        "stock": 80,
        "description": "Creamy milk chocolate bar",
        "unit": "bar"
    },
    "cookies": {
        "product_id": "PRD-003",
        "name": "Cookies",
        "category": "Snacks",
        "price": 29.99,
        "stock": 150,
        "description": "Crunchy chocolate chip cookies",
        "unit": "pack"
    },
    "biscuit": {
        "product_id": "PRD-004",
        "name": "Biscuit",
        "category": "Snacks",
        "price": 19.99,
        "stock": 200,
        "description": "Butter biscuits",
        "unit": "pack"
    },
    "juice": {
        "product_id": "PRD-005",
        "name": "Orange Juice",
        "category": "Beverages",
        "price": 59.99,
        "stock": 60,
        "description": "Fresh orange juice 1L",
        "unit": "bottle"
    },
    "water": {
        "product_id": "PRD-006",
        "name": "Water Bottle",
        "category": "Beverages",
        "price": 14.99,
        "stock": 300,
        "description": "Mineral water 1L",
        "unit": "bottle"
    },
    "chips": {
        "product_id": "PRD-007",
        "name": "Chips",
        "category": "Snacks",
        "price": 24.99,
        "stock": 120,
        "description": "Salted potato chips",
        "unit": "pack"
    }
}


def search_product(query: str):
    """Search for a product by name (fuzzy match)."""
    query_lower = query.lower().strip()

    # Exact match first
    if query_lower in PRODUCT_CATALOG:
        return PRODUCT_CATALOG[query_lower]

    # Partial match
    for key, product in PRODUCT_CATALOG.items():
        if query_lower in key or key in query_lower:
            return product

    # Name match
    for key, product in PRODUCT_CATALOG.items():
        if query_lower in product["name"].lower():
            return product

    return None


def get_all_products():
    """Return unique products from catalog."""
    seen = set()
    products = []
    for product in PRODUCT_CATALOG.values():
        if product["product_id"] not in seen:
            seen.add(product["product_id"])
            products.append(product)
    return products
