"""Tests for aipy_extracts"""
import os
import shutil
import nose.tools as nt
from .. import aipy_extracts as ae
from .. data import DATA_PATH


def test_bl2ij():
    """Test bl2ij function"""
    # small baseline number
    bl = 258
    nt.assert_true(ae.bl2ij(bl)[0] == 0)
    nt.assert_true(ae.bl2ij(bl)[1] == 1)

    # large baseline number
    bl = 67587
    nt.assert_true(ae.bl2ij(bl)[0] == 0)
    nt.assert_true(ae.bl2ij(bl)[1] == 2)
    return


def test_ij2bl():
    """Test ij2bl function"""
    # test < 256 antennas
    i = 1
    j = 2
    nt.assert_true(ae.ij2bl(i, j) == 515)

    # test > 256 antennas
    i = 2
    j = 257
    nt.assert_true(ae.ij2bl(i, j) == 71938)

    # test case where i > j
    i = 257
    j = 2
    nt.assert_true(ae.ij2bl(i, j) == 71938)
    return


def test_parse_ants():
    """Test parsing ant strings to tuples"""
    nants = 4
    cases = {
        'all': [],
        'auto': [('auto', 1)],
        'cross': [('auto', 0)],
        '0_1': [(ae.ij2bl(0, 1), 1)],
        '0_1,1_2': [(ae.ij2bl(0, 1), 1), (ae.ij2bl(1, 2), 1)],
        '0x_1x': [(ae.ij2bl(0, 1), 1, 'xx')],
        '(0x,0y)_1x': [(ae.ij2bl(0, 1), 1, 'xx'), (ae.ij2bl(0, 1), 1, 'yx')],
        '(0,1)_2': [(ae.ij2bl(0, 2), 1), (ae.ij2bl(1, 2), 1)],
        '0_(1,2)': [(ae.ij2bl(0, 1), 1), (ae.ij2bl(0, 2), 1)],
        '(0,1)_(2,3)': [(ae.ij2bl(0, 2), 1), (ae.ij2bl(0, 3), 1),
                        (ae.ij2bl(1, 2), 1), (ae.ij2bl(1, 3), 1)],
        '0_(1,-2)': [(ae.ij2bl(0, 1), 1), (ae.ij2bl(0, 2), 0)],
        '(-0,1)_(2,-3)': [(ae.ij2bl(0, 2), 0), (ae.ij2bl(0, 3), 0), (ae.ij2bl(1, 2), 1), (ae.ij2bl(1, 3), 0)],
        '0,1,all': [],
    }
    for i in range(nants):
        cases[str(i)] = map(lambda x: (ae.ij2bl(x, i), 1), range(nants))
        cases['-' + str(i)] = map(lambda x: (ae.ij2bl(x, i), 0), range(nants))
    # inelegantly paste on the new pol parsing flag on the above tests
    # XXX really should add some new tests for the new pol parsing
    for k in cases:
        cases[k] = [(v + (-1,))[:3] for v in cases[k]]
    for ant_str in cases:
        nt.assert_equal(ae.parse_ants(ant_str, nants),
                        cases[ant_str])

    # check that malformed antstr raises and error
    nt.assert_raises(ValueError, ae.parse_ants, '(0_1)_2', nants)
    return


def test_UV_wrhd_special():
    """Test _wrhd_special method on UV object"""
    test_file = os.path.join(DATA_PATH, 'test', 'miriad_test.uv')
    if os.path.exists(test_file):
        shutil.rmtree(test_file)
    uv = ae.UV(test_file, status='new', corrmode='r')
    freqs = [3, 1, 0.1, 0.2, 2, 0.2, 0.3, 3, 0.3, 0.4]
    uv._wrhd_special('freqs', freqs)

    # check that we wrote something to disk
    nt.assert_true(os.path.isdir(test_file))

    # check that anything besides 'freqs' raises an error
    nt.assert_raises(ValueError, uv._wrhd_special, 'foo', 12)

    # clean up after ourselves
    del uv
    shutil.rmtree(test_file)
    return


def test_UV_rdhd_special():
    """Test _rdhd_special method on UV object"""
    infile = os.path.join(DATA_PATH, 'zen.2456865.60537.xy.uvcRREAA')
    test_file = os.path.join(DATA_PATH, 'test', 'miriad_test.uv')
    if os.path.exists(test_file):
        shutil.rmtree(test_file)
    # make a new file using an old one as a template
    uv1 = ae.UV(infile)
    uv2 = ae.UV(test_file, status='new', corrmode='r')
    uv2.init_from_uv(uv1)

    # define freqs to write
    freqs = [3, 1, 0.1, 0.2, 2, 0.2, 0.3, 3, 0.3, 0.4]
    uv2._wrhd_special('freqs', freqs)

    # add a single record; otherwise, opening the file fails
    preamble, data = uv1.read()
    uv2.write(preamble, data)
    del uv1
    del uv2

    # open a new file and check that freqs match the written ones
    uv3 = ae.UV(test_file)
    freqs2 = uv3._rdhd_special('freqs')
    nt.assert_true(freqs == freqs2)

    # check that anything besides 'freqs' raises an error
    nt.assert_raises(ValueError, uv3._rdhd_special, 'foo')

    # cleean up after ourselves
    shutil.rmtree(test_file)
    return