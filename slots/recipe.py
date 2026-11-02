"""Slot 63 - Two-day recipe.

Day one prints a shopping list. Day two prints the simple, genuinely good recipe
those ingredients make. The gap is the point: you buy things without knowing
quite what for, and the reveal arrives the next morning.

**It must finish something tomorrow, so it pins.** On day one it records which
dish it chose and pins itself for the following date; on that date the engine
prints it whatever the tier and recency would have said. The three-part story
and the growing map are built on the same two calls.

**The recipe is Python's, not the narrator's.** A shopping list and a method are
facts in the way that matters most: quantities, oven temperatures and cooking
times that someone will follow with real food. A persona improvising "roast at a
brisk heat until it seems right" is a ruined dinner, and an invented temperature
for chicken is worse than ruined. Every dish here is written out in full and
prints verbatim; the persona names the section and nothing more.

**Only a real morning pins.** A `--date` simulation that promised tomorrow's
continuation would, when that date finally arrived, print the second half of a
meal nobody was ever told to shop for.
"""

from __future__ import annotations

from datetime import timedelta

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

NAMESPACE = "recipe"

# (key, dish, serves, ingredients, method). Deliberately short, forgiving and
# genuinely good - the brief in SLOTS.md is "simple", and a recipe that needs
# a mandoline is not simple.
DISHES: list[tuple[str, str, int, list[str], list[str]]] = [
    ("shakshuka", "Shakshuka", 2,
     ["1 onion", "1 red pepper", "2 cloves garlic", "1 tin chopped tomatoes",
      "4 eggs", "1 tsp cumin", "1 tsp smoked paprika", "bread to serve"],
     ["Soften sliced onion and pepper in oil, 8 minutes.",
      "Add garlic, cumin and paprika for 1 minute.",
      "Add tomatoes, season, simmer 10 minutes until thick.",
      "Make 4 hollows, crack in the eggs, cover.",
      "Cook on low 6-8 minutes until the whites set. Eat with bread."]),
    ("carbonara", "Spaghetti carbonara", 2,
     ["200g spaghetti", "100g pancetta or guanciale", "2 eggs",
      "50g pecorino or parmesan", "black pepper"],
     ["Boil the pasta in well-salted water.",
      "Fry the pancetta until crisp. Take off the heat.",
      "Beat eggs with the grated cheese and plenty of pepper.",
      "Drain the pasta, keeping a mug of the water.",
      "Off the heat, toss pasta with pancetta, then the egg. Loosen with the "
      "water. No cream, and no heat once the egg is in, or it scrambles."]),
    ("dal", "Red lentil dal", 3,
     ["200g red lentils", "1 onion", "3 cloves garlic", "thumb of ginger",
      "1 tin coconut milk", "1 tsp turmeric", "1 tsp garam masala",
      "rice to serve"],
     ["Soften chopped onion in oil, 8 minutes.",
      "Add grated garlic, ginger and the spices for 1 minute.",
      "Add rinsed lentils, coconut milk and 400ml water.",
      "Simmer 20 minutes, stirring, until soft and thick.",
      "Season well and serve over rice."]),
    ("traybake", "Chicken thigh traybake", 2,
     ["4 bone-in chicken thighs", "500g small potatoes", "1 lemon",
      "1 bulb garlic", "a few sprigs of thyme", "olive oil"],
     ["Heat the oven to 200C (180C fan).",
      "Halve the potatoes and toss with oil, salt, thyme and garlic cloves.",
      "Sit the thighs on top, skin up, with the lemon cut in wedges.",
      "Roast 45 minutes, until the skin is crisp.",
      "Chicken is done at 75C in the thickest part, or when the juices run "
      "clear. Squeeze the roasted lemon over."]),
    ("frittata", "Frittata for whatever is left", 2,
     ["6 eggs", "1 onion", "a handful of spinach", "100g cheese",
      "any cooked vegetables you have"],
     ["Soften the onion in an ovenproof pan.",
      "Add the vegetables and spinach until it wilts.",
      "Beat the eggs with half the cheese and pour in.",
      "Cook on low 8 minutes until the edges set.",
      "Scatter the rest of the cheese and finish under a hot grill, 3 minutes."]),
    ("risotto", "Mushroom risotto", 2,
     ["150g arborio rice", "250g mushrooms", "1 onion", "1 clove garlic",
      "750ml stock", "a glass of white wine", "40g parmesan", "butter"],
     ["Keep the stock hot in a pan.",
      "Fry the mushrooms hard until browned, set aside.",
      "Soften onion and garlic in butter, add rice for 1 minute.",
      "Add the wine, then the stock a ladle at a time, stirring, 18 minutes.",
      "Stir in mushrooms, parmesan and a knob of butter. Rest 2 minutes."]),
    ("tacos", "Black bean tacos", 2,
     ["1 tin black beans", "6 small tortillas", "1 red onion", "2 limes",
      "1 avocado", "1 tsp cumin", "fresh coriander"],
     ["Quick-pickle half the onion, sliced thin, in the juice of 1 lime.",
      "Fry the rest of the onion with cumin, add drained beans, mash roughly.",
      "Warm the tortillas in a dry pan.",
      "Mash the avocado with lime and salt.",
      "Fill with beans, avocado, pickled onion and coriander."]),
]


@register
class TwoDayRecipe(Slot):
    spec = SlotSpec(id=63, name="Two-day recipe", tier="uncommon", paper_mm=44,
                    needs_narrator=True)

    def _state(self, ctx: Context) -> dict | None:
        if ctx.store is None:
            return None
        try:
            return ctx.store.fetch(NAMESPACE, "running")
        except Exception:  # noqa: BLE001
            return None

    def _dish(self, key: str):
        return next((d for d in DISHES if d[0] == key), None)

    def _day_two(self, dish) -> SlotResult:
        _, name, serves, ingredients, method = dish
        steps = "".join(f"<li>{s}</li>" for s in method)
        return SlotResult(
            head="The Recipe",
            body=f'{_CSS}<div class="recipe-name">{name}</div>'
                 f'<div class="recipe-serves">serves {serves}</div>'
                 f'<ol class="recipe-steps">{steps}</ol>',
            fine="Yesterday's shopping list, explained.",
            brief={"verbatim": True, "dish": name, "day": 2,
                   "instruction": "Name this section in voice - it is the reveal "
                                  "of what yesterday's shopping list was for. "
                                  "The recipe prints exactly as written: its "
                                  "quantities, times and temperatures are not "
                                  "yours to change."},
        )

    def _day_one(self, ctx: Context) -> SlotResult:
        dish = ctx.rng(self.spec.id).choice(DISHES)
        key, _, serves, ingredients, _ = dish

        if ctx.shared.get("real_morning") and ctx.store is not None:
            from selection import pin
            tomorrow = ctx.date + timedelta(days=1)
            ctx.store.put(NAMESPACE, "running",
                          {"dish": key, "reveal": tomorrow.isoformat()})
            pin(ctx.store, self.spec.id, tomorrow)

        items = "".join(f'<div class="shop-row"><span class="shop-box"></span>'
                        f'<span>{i}</span></div>' for i in ingredients)
        return SlotResult(
            head="Shopping List",
            body=f'{_CSS}{items}',
            # Deliberately does not name the dish. The reveal is tomorrow.
            fine=f"For {serves}. What it is for arrives tomorrow.",
            brief={"verbatim": True, "day": 1,
                   "instruction": "Name this section in voice. It is a shopping "
                                  "list for a dish that will be revealed tomorrow "
                                  "- do NOT name or guess the dish, and do not "
                                  "change any item on the list."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        state = self._state(ctx)
        if state and state.get("reveal") == ctx.date.isoformat():
            dish = self._dish(state.get("dish", ""))
            if dish:
                if ctx.shared.get("real_morning") and ctx.store is not None:
                    ctx.store.put(NAMESPACE, "running", None)
                return self._day_two(dish)
        return self._day_one(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._day_one(ctx)


_CSS = """
<style>
/* A shopping list you can tick in the shop, so every item gets a box. */
.shop-row    { display: flex; align-items: center; gap: 9px; margin: 3px 0; }
.shop-box    { flex: 0 0 auto; width: 13px; height: 13px;
               border: 2px solid #000; }
.recipe-name { font-size: calc(var(--size-body) + 4px);
               font-weight: var(--bold); line-height: 1.2; }
.recipe-serves { font-size: var(--size-tiny); letter-spacing: 0.1em;
                 text-transform: uppercase; margin-bottom: 4px; }
/* Numbered steps with the number hung in the margin, the way a recipe card
   does it, so each step starts on a clean edge. */
.recipe-steps { margin: 4px 0 0; padding-left: 1.6em; }
.recipe-steps li { margin: 3px 0; padding-left: 2px; }
</style>
"""
