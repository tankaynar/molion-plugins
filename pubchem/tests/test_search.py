"""pubchem_search.search on recorded answers."""

from conftest import FakePubChem, fixture, props

from pubchem_search import search as pubchem


def test_exact_name_comes_first_even_when_autocomplete_ranks_it_tenth(heme_pubchem):
    results = pubchem.search('heme', heme_pubchem)
    assert [r['cid'] for r in results[:4]] == [26945, 4973, 444098, 444097]
    assert all(r['matched'] == 'heme' for r in results[:4])
    assert results[0]['name'] == 'Hemin'
    assert results[0]['smiles'].endswith('.[Fe+2]')
    assert 'matched' not in results[4]


def test_suggestions_follow_and_keep_their_own_names(heme_pubchem):
    results = pubchem.search('heme', heme_pubchem)
    assert [r['name'] for r in results[4:]] == ['Hemellitic acid', 'Hemellitol', 'Hemel', 'Hemetoidin']


def test_one_property_request_describes_every_hit(heme_pubchem):
    pubchem.search('heme', heme_pubchem)
    property_calls = [url for url in heme_pubchem.calls if '/property/' in url]
    assert len(property_calls) == 1
    assert '26945,4973,444098,444097,10708,10686,3604,5280352' in property_calls[0]


def test_limit_caps_the_results(heme_pubchem):
    assert len(pubchem.search('heme', heme_pubchem, limit=3)) == 3


def test_a_number_is_a_cid():
    fake = FakePubChem({'/compound/cid/2244/property/': {'PropertyTable': {'Properties': [
        props(2244, 'Aspirin', 'CC(=O)OC1=CC=CC=C1C(=O)O', 'C9H8O4')]}}})
    results = pubchem.search('2244', fake)
    assert [r['name'] for r in results] == ['Aspirin']
    assert not any('autocomplete' in url for url in fake.calls)


def test_an_inchikey_is_looked_up_as_one():
    key = 'BSYNRYMUTXBXSQ-UHFFFAOYSA-N'
    fake = FakePubChem({f'/inchikey/{key}/cids': {'IdentifierList': {'CID': [2244]}},
                        '/property/': {'PropertyTable': {'Properties': [props(2244, 'Aspirin')]}}})
    assert [r['cid'] for r in pubchem.search(key, fake)] == [2244]


def test_an_unknown_name_finds_nothing():
    assert pubchem.search('qqqzzz', FakePubChem({})) == []


def test_legacy_smiles_property_names_are_still_read():
    fake = FakePubChem({'/property/': {'PropertyTable': {'Properties': [
        {'CID': 702, 'Title': 'Ethanol', 'CanonicalSMILES': 'CCO', 'MolecularWeight': '46.07'}]}}})
    assert pubchem.search('702', fake)[0]['smiles'] == 'CCO'


def test_an_all_capitals_name_is_put_in_title_case():
    assert pubchem.display_name('TETRAHYDROFURAN') == 'Tetrahydrofuran'
    assert pubchem.display_name('aspirin') == 'Aspirin'
    assert pubchem.display_name('DMF') == 'DMF'


def test_the_record_is_cut_at_its_end_line():
    fake = FakePubChem({'/compound/cid/26945/SDF?record_type=2d': fixture('heme-26945-2d.sdf')})
    record = pubchem.record_2d(26945, fake)
    assert record.rstrip().endswith('M  END')
    assert '$$$$' not in record and '> <PUBCHEM' not in record


def test_a_cid_without_a_drawing_is_not_found():
    try:
        pubchem.record_2d(1, FakePubChem({}))
    except pubchem.NotFound:
        return
    raise AssertionError('expected NotFound')
