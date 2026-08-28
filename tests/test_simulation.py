from backend.simulation import Simulation


def test_simulation_packet_has_world_state():
    simulation = Simulation()
    packet = simulation.packet()
    assert len(packet["specimens"]) == 42
    assert packet["teleporter"]["x"] == 500
    assert {zone["name"] for zone in packet["zones"]} == {"cafe", "bar", "church", "forest", "homes", "pop_up"}
    assert sum(not specimen["is_homeless"] for specimen in packet["specimens"]) == 20
    assert all(specimen["new_arrival"] for specimen in packet["specimens"])
    assert packet["simulation_number"] == 1
    assert all(specimen["name"] for specimen in packet["specimens"])
    forest = next(zone for zone in packet["zones"] if zone["name"] == "forest")
    assert (forest["x"], forest["y"], forest["width"], forest["height"]) == (750, 0, 250, 1000)
    assert len(packet["animals"]) == 18
    assert sum(animal["species"] == "deer" for animal in packet["animals"]) == 14
    assert sum(animal["species"] == "bear" for animal in packet["animals"]) == 4
    assert len(packet["plants"]) == 34


def test_forest_resources_stay_in_forest_and_plants_regrow():
    simulation = Simulation()
    forest = next(zone for zone in simulation.world.zones if zone.name == "forest")
    plant = next(resource for resource in simulation.world.resources.values() if resource.kind == "plant")
    plant.energy = 1
    simulation.world.grow_plants(10)
    assert plant.energy > 1
    assert forest.contains(plant.position)
    assert all(forest.contains(resource.position) for resource in simulation.world.resources.values())


def test_night_shelter_intent_prefers_home_or_forest():
    simulation = Simulation()
    simulation.elapsed_seconds = 20 * 25
    housed = next(specimen for specimen in simulation.specimens.values() if specimen.home)
    homeless = next(specimen for specimen in simulation.specimens.values() if specimen.is_homeless)
    assert simulation.behavior.choose(housed, simulation) == "return_home"
    assert simulation.behavior.choose(homeless, simulation) == "explore"


def test_simulation_advances_and_keeps_positions_in_bounds():
    simulation = Simulation()
    initial_tick = simulation.tick
    simulation.step()
    assert simulation.tick == initial_tick + 1
    assert all(0 <= specimen.position[0] <= 1000 and 0 <= specimen.position[1] <= 1000 for specimen in simulation.specimens.values())


def test_new_arrival_indicator_expires_after_first_simulated_day():
    simulation = Simulation()
    specimen = simulation.specimens[1]
    specimen.age_hours = 24
    simulation.step()
    assert specimen.new_arrival is False


def test_animals_have_visible_roaming_motion():
    simulation = Simulation()
    animal = next(resource for resource in simulation.world.resources.values() if resource.kind == "animal")
    start = animal.position
    simulation.world.move_animals(0.1)
    assert animal.position != start
    assert simulation.world.zone_at(animal.position) == "forest"


def test_homeless_agent_sells_forest_goods_at_cafe():
    simulation = Simulation()
    specimen = next(agent for agent in simulation.specimens.values() if agent.is_homeless)
    specimen.plant_goods = 2
    specimen.animal_goods = 1
    specimen.position = (150, 150)
    starting_wallet = specimen.wallet
    simulation.sell_goods_at_cafe(specimen)
    assert specimen.wallet == starting_wallet + 22
    assert specimen.plant_goods == 0 and specimen.animal_goods == 0


def test_homeless_agent_can_negotiate_home_from_owner():
    simulation = Simulation()
    specimen = next(agent for agent in simulation.specimens.values() if agent.is_homeless)
    seller = next(agent for agent in simulation.specimens.values() if agent.home)
    specimen.wallet = 60
    specimen.position = (150, 150)
    seller.wallet = 10
    previous_home = seller.home
    simulation.buy_or_negotiate_home(specimen)
    assert specimen.is_homeless is False
    assert specimen.home == previous_home
    assert seller.is_homeless is True


def test_reset_starts_a_new_numbered_simulation():
    simulation = Simulation()
    simulation.step()
    simulation.reset_population()
    assert simulation.packet()["simulation_number"] == 2
    assert simulation.packet()["tick"] == 0


def test_poisonous_plant_can_kill_an_agent():
    simulation = Simulation()
    specimen = next(iter(simulation.specimens.values()))
    plant = next(resource for resource in simulation.world.resources.values() if resource.kind == "plant")
    plant.poisonous = True
    forest = next(zone for zone in simulation.world.zones if zone.name == "forest")
    specimen.position = plant.position = (forest.x + 20, forest.y + 20)
    simulation._resolve_forest_food(specimen)
    assert specimen.alive is False
    assert specimen.current_action == "ate_poisonous_plant"


def test_animals_roam_but_plants_stay_rooted():
    simulation = Simulation()
    animal = next(resource for resource in simulation.world.resources.values() if resource.kind == "animal")
    plant = next(resource for resource in simulation.world.resources.values() if resource.kind == "plant")
    plant_position = plant.position
    animal_position = animal.position
    simulation.world.move_animals()
    assert plant.position == plant_position
    assert animal.position != animal_position


def test_add_specimen_assigns_requested_apartment_and_values():
    simulation = Simulation()
    specimen = simulation.add_specimen({"gender": "woman", "housed": True, "friendliness": 99, "speed": 12, "hunger": 4})
    assert specimen.gender == "woman"
    assert specimen.home is None
    assert specimen.is_homeless is True
    assert specimen.personality.friendliness == 99
    assert specimen.genetics.speed == 12
    assert specimen.hunger == 4


def test_specimens_can_choose_to_donate_to_nearby_homeless_agent():
    simulation = Simulation()
    donor = next(agent for agent in simulation.specimens.values() if not agent.is_homeless)
    recipient = next(agent for agent in simulation.specimens.values() if agent.is_homeless)
    donor.position = (400, 400)
    recipient.position = (420, 400)
    donor.wallet = 20
    recipient.wallet = 0
    donor.personality.morality = 100
    assert simulation.donate_to_homeless(donor) is True
    assert donor.wallet == 15
    assert recipient.wallet == 5
    assert donor.current_action == "donated"


def test_names_do_not_change_behavior_decisions():
    simulation = Simulation()
    first = next(agent for agent in simulation.specimens.values() if agent.home)
    second = next(agent for agent in simulation.specimens.values() if agent.home and agent.id != first.id)
    second.personality = first.personality
    second.genetics = first.genetics
    second.hunger = first.hunger
    second.fatigue = first.fatigue
    second.wallet = first.wallet
    first.name = "Amina"
    second.name = "Zhang"
    assert simulation.behavior.choose(first, simulation) == simulation.behavior.choose(second, simulation)


def test_homeless_team_can_build_shared_forest_shelter():
    simulation = Simulation()
    forest = next(zone for zone in simulation.world.zones if zone.name == "forest")
    team = [agent for agent in simulation.specimens.values() if agent.is_homeless][:2]
    for index, agent in enumerate(team):
        agent.position = (forest.x + 40 + index * 10, forest.y + 100)
        agent.plant_goods = 1
    assert simulation.build_forest_shelter(team[0]) is True
    assert all(agent.is_homeless is False for agent in team)
    assert all(agent.home_kind == "forest_shelter" for agent in team)
    assert team[0].home == team[1].home
    assert forest.contains(team[0].home)


def test_hungry_agent_moves_toward_cafe_to_eat():
    simulation = Simulation()
    specimen = simulation.specimens[1]
    specimen.hunger = 95
    specimen.position = (900, 500)
    start = specimen.position
    simulation.behavior.execute(specimen, "eat", simulation)
    assert specimen.position != start


def test_hunger_does_not_empty_population_in_a_few_seconds():
    simulation = Simulation()
    for _ in range(100):
        simulation.step()
    assert len(simulation.specimens) > 0


def test_human_death_creates_canvas_marker_data():
    simulation = Simulation()
    specimen = simulation.specimens[1]
    specimen.hunger = 100
    simulation.step()
    marker = next(marker for marker in simulation.packet()["death_markers"] if marker["name"] == specimen.name)
    assert (marker["x"], marker["y"]) == (round(specimen.position[0], 1), round(specimen.position[1], 1))
    assert marker["entity_type"] == "human"
    assert marker["cause"] == "starvation"


def test_hunted_animal_creates_death_marker_data():
    simulation = Simulation()
    specimen = simulation.specimens[1]
    specimen.genetics.speed = 100
    animal = next(resource for resource in simulation.world.resources.values() if resource.kind == "animal")
    forest = next(zone for zone in simulation.world.zones if zone.name == "forest")
    specimen.position = animal.position = (forest.x + 20, forest.y + 20)
    simulation._resolve_forest_food(specimen)
    marker = next(marker for marker in simulation.packet()["death_markers"] if marker["cause"] == "hunted")
    assert marker["entity_type"] == "animal"


def test_bear_eats_deer_and_poison_madness_lasts_two_simulated_hours():
    simulation = Simulation()
    bear = next(resource for resource in simulation.world.resources.values() if resource.species == "bear")
    deer = next(resource for resource in simulation.world.resources.values() if resource.species == "deer")
    deer.position = bear.position
    simulation._resolve_bear_behavior(0.1)
    assert deer.id not in simulation.world.resources
    plant = next(resource for resource in simulation.world.resources.values() if resource.kind == "plant")
    plant.poisonous = True
    plant.position = bear.position
    simulation._resolve_bear_behavior(0.1)
    assert bear.mad_remaining_hours == 2.0
    simulation._resolve_bear_behavior(50.0)
    assert bear.mad_remaining_hours == 0.0


def test_deer_eat_plants_but_die_from_poisonous_plants():
    simulation = Simulation()
    deer = next(resource for resource in simulation.world.resources.values() if resource.species == "deer")
    plant = next(resource for resource in simulation.world.resources.values() if resource.kind == "plant")
    deer.position = plant.position
    plant.poisonous = True
    simulation._resolve_deer_feeding()
    assert deer.id not in simulation.world.resources
