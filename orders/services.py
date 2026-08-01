"""Turns an approved MenuPlan into supplier orders and farmer demand signals."""
from collections import defaultdict
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

from nutrition.utils import best_price_for_ingredient
from suppliers.models import SupplierListing
from farmers.models import DemandSignal, Farmer
from configuration.models import SystemConfiguration
from notifications.models import Notification
from notifications.services import notify, notify_many
from core.geo import estimate_distance_and_eta, county_location
from .models import ProduceOrder, ProduceOrderItem


def _platform_margin_rate() -> Decimal:
    """Reads the current procurement margin from the admin-managed system configuration."""
    percent = SystemConfiguration.load().platform_margin_percent
    return (percent / Decimal("100"))


def _aggregate_ingredient_needs(menu_plan):
    """Sum raw ingredient quantities needed across every menu item in the plan."""
    needs = defaultdict(Decimal)
    for item in menu_plan.items.select_related("recipe").all():
        for ri in item.recipe.recipeingredient_set.select_related("ingredient").all():
            needs[ri.ingredient] += ri.quantity_per_portion * item.servings
    return needs


def _institution_weekly_budget_total(institution):
    """
    The institution's full week budget, for the WHOLE institution (not per person), across
    only the meals it actually offers — so it's a fair comparison against a recommended
    order total, which is likewise for the whole institution's headcount.
    """
    headcount = institution.headcount or 1
    per_meal_budgets = [
        institution.budget_breakfast, institution.budget_lunch, institution.budget_supper,
    ]
    configured = [b for b in per_meal_budgets if b is not None]
    if configured:
        per_person_daily = sum(configured)
    else:
        per_person_daily = (institution.budget_per_meal or Decimal("0")) * 3
    return per_person_daily * 7 * headcount


def generate_orders_and_demand_signals(menu_plan):
    institution = menu_plan.institution
    county = institution.county
    needs = _aggregate_ingredient_needs(menu_plan)

    orders_by_supplier = {}
    created_orders = []

    for ingredient, quantity in needs.items():
        listing = (
            SupplierListing.objects.filter(ingredient=ingredient, is_active=True, supplier__county__iexact=county)
            .order_by("price_per_unit").first()
            or SupplierListing.objects.filter(ingredient=ingredient, is_active=True).order_by("price_per_unit").first()
        )

        # Always create a demand signal, even without an active supplier match,
        # so farmers see the forecast and can respond ahead of a listing existing.
        DemandSignal.objects.create(
            ingredient=ingredient,
            forecast_quantity=quantity,
            county=county,
            window_start=menu_plan.week_start,
            window_end=menu_plan.week_start + timedelta(days=6),
            source_menu_plan=menu_plan,
        )

        if not listing:
            continue

        supplier = listing.supplier
        if supplier.id not in orders_by_supplier:
            order = ProduceOrder.objects.create(
                institution=institution, menu_plan=menu_plan, supplier=supplier, status=ProduceOrder.Status.PENDING,
            )
            orders_by_supplier[supplier.id] = order
            created_orders.append(order)
        order = orders_by_supplier[supplier.id]

        price = listing.price_per_unit
        subtotal = quantity * price
        ProduceOrderItem.objects.create(
            order=order, ingredient=ingredient, quantity=quantity, unit_price=price, subtotal=subtotal,
        )

    margin_rate = _platform_margin_rate()
    for order in created_orders:
        subtotal = sum((i.subtotal for i in order.items.all()), start=Decimal("0"))
        margin = round(subtotal * margin_rate, 2)
        order.total_value = subtotal + margin
        order.platform_margin = margin
        order.save()

    menu_plan.status = menu_plan.Status.APPROVED
    menu_plan.approved_at = timezone.now()
    menu_plan.save()

    # ---- Notifications ----
    # Institution: one summary notification for the whole approved menu (not one per order).
    if created_orders:
        supplier_names = ", ".join(sorted({o.supplier.name for o in created_orders}))
        notify(
            institution.user,
            "Menu approved — orders placed",
            f"Your menu for the week of {menu_plan.week_start} generated {len(created_orders)} "
            f"order(s) with: {supplier_names}.",
            notification_type=Notification.NotificationType.MENU_APPROVED,
            level=Notification.Level.SUCCESS,
            link="/institution/orders",
        )
    else:
        notify(
            institution.user,
            "Menu approved — no suppliers matched",
            f"Your menu for the week of {menu_plan.week_start} was approved, but no active "
            f"supplier listings matched its ingredients yet. Demand signals were still sent to farmers.",
            notification_type=Notification.NotificationType.MENU_APPROVED,
            level=Notification.Level.WARNING,
            link="/institution/menus",
        )

    # Supplier: one notification per supplier that received an order.
    for order in created_orders:
        item_count = order.items.count()
        notify(
            order.supplier.user,
            "New produce order received",
            f"{institution.name} placed an order for {item_count} ingredient(s) worth "
            f"KSh {order.total_value:,.2f}.",
            notification_type=Notification.NotificationType.ORDER_PLACED,
            level=Notification.Level.INFO,
            related_order=order,
            link="/supplier/orders",
        )

    # Farmers: notify farmers in the same county that a new demand signal is available.
    county_farmers = Farmer.objects.filter(county__iexact=county).select_related("user") if county else Farmer.objects.none()
    if county_farmers.exists() and needs:
        ingredient_names = ", ".join(sorted({i.name for i in needs.keys()})[:5])
        notify_many(
            [f.user for f in county_farmers],
            "New demand signal in your county",
            f"Institutions in {county} are forecasting demand for: {ingredient_names}.",
            notification_type=Notification.NotificationType.DEMAND_SIGNAL,
            level=Notification.Level.INFO,
            link="/farmer/demand",
        )

    return created_orders


# ---------------------------------------------------------------------------
# Recommend-then-let-the-institution-decide workflow.
#
# generate_orders_and_demand_signals() above auto-picks the cheapest supplier for
# every ingredient and places orders immediately — useful for scripted/demo data,
# but not what a real institution wants: they should see who's offering what, at
# what price, from where, and choose the supplier per ingredient themselves. These
# three functions implement that as separate steps:
#   1. approve_menu_plan()          — menu is nutritionally locked in; demand
#                                      signals go out to farmers; NO orders yet.
#   2. get_supplier_recommendations() — read-only: every ingredient the plan needs,
#                                      every supplier offering it (location + price),
#                                      and which one the AI recommends (cheapest).
#   3. place_orders_from_selection() — the institution's own supplier choices are
#                                      turned into real orders.
# ---------------------------------------------------------------------------

def build_order_tracking(order):
    """
    Everything the order-tracking UI needs: WHERE the supplier and institution are (static
    points, for a map — not a live-moving delivery pin), how far apart they are and the
    estimated delivery time, and a step-by-step status timeline (place → confirm → deliver,
    or cancelled) with timestamps where known. This is the "oraimo style" courier-tracking
    pattern: fixed checkpoints with timestamps, not GPS breadcrumb tracking of the vehicle.
    """
    supplier_location = county_location(order.supplier.county)
    institution_location = county_location(order.institution.county)
    geo = estimate_distance_and_eta(order.supplier.county, order.institution.county)

    if order.status == ProduceOrder.Status.CANCELLED:
        steps = [
            {"key": "placed", "label": "Order placed", "done": True, "timestamp": order.created_at},
            {"key": "cancelled", "label": "Order cancelled", "done": True, "timestamp": order.cancelled_at},
        ]
    else:
        steps = [
            {"key": "placed", "label": "Order placed", "done": True, "timestamp": order.created_at},
            {
                "key": "confirmed", "label": "Confirmed by supplier",
                "done": order.status in (ProduceOrder.Status.CONFIRMED, ProduceOrder.Status.DELIVERED),
                "timestamp": order.confirmed_at,
            },
            {
                "key": "delivered", "label": "Delivered",
                "done": order.status == ProduceOrder.Status.DELIVERED,
                "timestamp": order.delivered_at,
            },
        ]

    return {
        "order_id": order.id,
        "status": order.status,
        "supplier_location": supplier_location,
        "institution_location": institution_location,
        "distance_km": geo["distance_km"],
        "estimated_delivery_hours": geo["estimated_delivery_hours"],
        "steps": steps,
    }


def approve_menu_plan(menu_plan):
    """Lock in a draft menu plan and notify farmers of the resulting demand — without
    picking suppliers or creating orders. Returns the aggregated ingredient needs."""
    institution = menu_plan.institution
    county = institution.county
    needs = _aggregate_ingredient_needs(menu_plan)

    for ingredient, quantity in needs.items():
        DemandSignal.objects.create(
            ingredient=ingredient, forecast_quantity=quantity, county=county,
            window_start=menu_plan.week_start, window_end=menu_plan.week_start + timedelta(days=6),
            source_menu_plan=menu_plan,
        )

    menu_plan.status = menu_plan.Status.APPROVED
    menu_plan.approved_at = timezone.now()
    menu_plan.save()

    notify(
        institution.user,
        "Menu approved — pick your suppliers",
        f"Your menu for the week of {menu_plan.week_start} is locked in. Review the recommended "
        f"suppliers and prices, then place your orders whenever you're ready.",
        notification_type=Notification.NotificationType.MENU_APPROVED,
        level=Notification.Level.SUCCESS,
        link=f"/institution/menus",
    )

    county_farmers = Farmer.objects.filter(county__iexact=county).select_related("user") if county else Farmer.objects.none()
    if county_farmers.exists() and needs:
        ingredient_names = ", ".join(sorted({i.name for i in needs.keys()})[:5])
        notify_many(
            [f.user for f in county_farmers],
            "New demand signal in your county",
            f"Institutions in {county} are forecasting demand for: {ingredient_names}.",
            notification_type=Notification.NotificationType.DEMAND_SIGNAL,
            level=Notification.Level.INFO,
            link="/farmer/demand",
        )
    return needs


def get_supplier_recommendations(menu_plan):
    """
    Read-only. For every ingredient the plan needs: every active supplier listing
    (any county — nearest/cheapest first), with the AI's recommended (cheapest)
    pick flagged, plus a total comparing the fully-recommended cost against the
    institution's weekly budget. Nothing here is persisted or auto-selected.
    """
    institution = menu_plan.institution
    county = institution.county
    needs = _aggregate_ingredient_needs(menu_plan)

    items = []
    recommended_total = Decimal("0")
    unmatched = []

    for ingredient, quantity in sorted(needs.items(), key=lambda kv: kv[0].name):
        listings = list(
            SupplierListing.objects.filter(ingredient=ingredient, is_active=True)
            .select_related("supplier")
            .order_by("price_per_unit")
        )
        options = []
        cheapest_id = listings[0].supplier_id if listings else None
        for listing in listings:
            geo = estimate_distance_and_eta(listing.supplier.county, county)
            options.append({
                "supplier_id": listing.supplier_id,
                "supplier_name": listing.supplier.name,
                "county": listing.supplier.county,
                "same_county": bool(county) and listing.supplier.county.lower() == county.lower(),
                "distance_km": geo["distance_km"],
                "estimated_delivery_hours": geo["estimated_delivery_hours"],
                "price_per_unit": listing.price_per_unit,
                "quantity_available": listing.quantity_available,
                "subtotal": round(quantity * listing.price_per_unit, 2),
                "is_recommended": listing.supplier_id == cheapest_id,
            })
        if not options:
            unmatched.append(ingredient.name)
        else:
            recommended_total += options[0]["subtotal"]

        items.append({
            "ingredient_id": ingredient.id,
            "ingredient_name": ingredient.name,
            "unit": ingredient.unit,
            "quantity_needed": quantity,
            "recommended_supplier_id": cheapest_id,
            "options": options,
        })

    weekly_budget = _institution_weekly_budget_total(institution)
    margin_rate = _platform_margin_rate()
    recommended_total_with_margin = round(recommended_total * (1 + margin_rate), 2)

    return {
        "items": items,
        "unmatched_ingredients": unmatched,
        "recommended_subtotal": round(recommended_total, 2),
        "recommended_total_with_platform_margin": recommended_total_with_margin,
        "weekly_budget_total": round(weekly_budget, 2),
        "savings_vs_budget": round(weekly_budget - recommended_total_with_margin, 2) if weekly_budget else None,
    }


def place_orders_from_selection(menu_plan, selections):
    """
    Turn the institution's own supplier choices into real orders.
    `selections` is {ingredient_id (int): supplier_id (int)}, one entry per ingredient
    the menu plan needs that has at least one active listing. Raises ValueError with a
    human-readable message if a selection is missing or no longer valid (e.g. the
    listing went inactive between recommendation and checkout).
    """
    institution = menu_plan.institution
    needs = _aggregate_ingredient_needs(menu_plan)
    needs_by_id = {ing.id: (ing, qty) for ing, qty in needs.items()}

    orders_by_supplier = {}
    created_orders = []

    for ingredient_id, (ingredient, quantity) in needs_by_id.items():
        available = SupplierListing.objects.filter(ingredient=ingredient, is_active=True).exists()
        if not available:
            continue  # nothing to order — demand signal already covers it
        supplier_id = selections.get(ingredient_id) or selections.get(str(ingredient_id))
        if not supplier_id:
            raise ValueError(f"No supplier chosen for {ingredient.name}.")
        listing = SupplierListing.objects.filter(
            ingredient=ingredient, supplier_id=supplier_id, is_active=True
        ).select_related("supplier").first()
        if not listing:
            raise ValueError(f"The chosen supplier for {ingredient.name} is no longer available. Please re-check recommendations.")

        supplier = listing.supplier
        if supplier.id not in orders_by_supplier:
            order = ProduceOrder.objects.create(
                institution=institution, menu_plan=menu_plan, supplier=supplier, status=ProduceOrder.Status.PENDING,
            )
            orders_by_supplier[supplier.id] = order
            created_orders.append(order)
        order = orders_by_supplier[supplier.id]

        price = listing.price_per_unit
        subtotal = quantity * price
        ProduceOrderItem.objects.create(
            order=order, ingredient=ingredient, quantity=quantity, unit_price=price, subtotal=subtotal,
        )

    margin_rate = _platform_margin_rate()
    for order in created_orders:
        subtotal = sum((i.subtotal for i in order.items.all()), start=Decimal("0"))
        margin = round(subtotal * margin_rate, 2)
        order.total_value = subtotal + margin
        order.platform_margin = margin
        order.save()

    menu_plan.status = menu_plan.Status.ORDERED
    menu_plan.save()

    if created_orders:
        supplier_names = ", ".join(sorted({o.supplier.name for o in created_orders}))
        notify(
            institution.user,
            "Orders placed",
            f"Your orders for the week of {menu_plan.week_start} were placed with: {supplier_names}.",
            notification_type=Notification.NotificationType.ORDER_PLACED,
            level=Notification.Level.SUCCESS,
            link="/institution/orders",
        )
    for order in created_orders:
        item_count = order.items.count()
        notify(
            order.supplier.user,
            "New produce order received",
            f"{institution.name} placed an order for {item_count} ingredient(s) worth "
            f"KSh {order.total_value:,.2f}.",
            notification_type=Notification.NotificationType.ORDER_PLACED,
            level=Notification.Level.INFO,
            related_order=order,
            link="/supplier/orders",
        )
    return created_orders
