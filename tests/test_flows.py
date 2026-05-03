import numpy as np

from powerflow import Branch, Bus, Case, compute_branch_flows


def test_branch_flows_are_equal_and_opposite_on_lossless_flat_line():
    """A lossless line at flat voltage has zero flow and zero loss."""
    case = Case(
        base_mva=100.0,
        buses=[
            Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            Bus(2, "pq", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        ],
        branches=[Branch(1, 2, r=0.0, x=0.2, b=0.0)],
    )

    flow = compute_branch_flows(case, np.array([1.0, 1.0]), np.array([0.0, 0.0]))[0]

    assert flow.p_from == 0.0
    assert flow.q_from == 0.0
    assert flow.p_to == 0.0
    assert flow.q_to == 0.0
    assert flow.p_loss == 0.0
    assert flow.q_loss == 0.0


def test_branch_flow_losses_equal_sum_of_terminal_flows():
    """Branch losses are the sum of from-end and to-end complex powers."""
    case = Case(
        base_mva=100.0,
        buses=[
            Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            Bus(2, "pq", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        ],
        branches=[Branch(1, 2, r=0.02, x=0.04, b=0.0)],
    )

    flow = compute_branch_flows(case, np.array([1.0, 0.98]), np.array([0.0, -0.1]))[0]

    np.testing.assert_allclose(flow.p_loss, flow.p_from + flow.p_to)
    np.testing.assert_allclose(flow.q_loss, flow.q_from + flow.q_to)
