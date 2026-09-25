from training.icmyc import build_text, map_category, mask_pii


def test_maps_subcategories_onto_our_categories():
    assert map_category("Mobility - Roads, Footpaths and Infrastructure", "Fixing/Reparing Potholes") == "pothole_road"
    assert map_category("Streetlights", "Maintenance/Repair Of Streetlights") == "streetlight"
    assert map_category("Sewerage Systems", "Maintenance And Repair Of Manholes") == "drainage_sewage"
    assert map_category("Yellow Spot", "Report A Broken Footpath") == "footpath"
    assert map_category("Animal Husbandry", "Stray Dog Sterilisation/Animal Birth Control (ABC)") == "other"


def test_ambiguous_or_unknown_rows_are_dropped_not_guessed():
    assert map_category("Others", "Others") is None
    assert map_category("NULL", "NULL") is None
    assert map_category("Mobility - Roads, Footpaths and Infrastructure",
                        "Flooding/Waterlogging Of Roads And Footpaths") is None


def test_masks_phone_email_numbers_and_signoff_names():
    text = ("Garbage not cleared near 5th cross, Bangalore 560043. Call 98450 12345 "
            "or +91-9845012345 or mail ravi.k@gmail.com. Mr. Ravi Kumar complained too.\n"
            "Regards,\nRavi Kumar")
    masked = mask_pii(text)
    assert "98450" not in masked and "9845012345" not in masked
    assert "gmail" not in masked
    assert "560043" not in masked
    assert "Ravi" not in masked
    assert masked.startswith("Garbage not cleared near 5th cross")


def test_signoff_with_lowercase_name_and_phone_is_cut_but_in_regards_to_is_kept():
    assert mask_pii("Please do fix it. Regards Anil kumar k 9845012345") == "Please do fix it."
    kept = "This complaint is in regards to the AET junction, which floods every monsoon season."
    assert mask_pii(kept) == kept


def test_title_that_is_just_the_category_name_is_not_used():
    # Would leak the label into the training text.
    assert build_text("Garbage Dump", "Pile of waste near the park", "Garbage Dump") == "Pile of waste near the park"


def test_truncated_title_that_repeats_description_is_not_duplicated():
    desc = "The storm water drain near 2nd cross is blocked and the basement floods"
    assert build_text("The storm water drain near 2nd cross is blo...", desc, "x") == desc


def test_informative_title_is_kept():
    assert build_text("Deadly road condition", "Road is covered with sand at the turning", "x") == \
        "Deadly road condition. Road is covered with sand at the turning"
