from .account_tools import (
    get_account_info,
    get_portfolio_history,
)

from .market_tools import (
    get_market_clock,
)

from .asset_tools import (
    get_asset_info,
    is_asset_tradable,
)

from .position_tools import (
    get_all_positions,
    get_open_position,
    close_position,
    close_all_positions,
)

from .order_tools import (
    place_market_order,
    place_limit_order,
    place_stop_order,
    place_stop_limit_order,
    place_trailing_stop_order,
    place_bracket_market_order,
    get_orders,
    get_order_by_id,
    replace_order,
    cancel_order,
    cancel_all_orders,
)


READ_ONLY_TOOLS = [
    get_account_info,
    get_portfolio_history,
    get_market_clock,
    get_asset_info,
    is_asset_tradable,
    get_all_positions,
    get_open_position,
    get_orders,
    get_order_by_id,
]


EXECUTION_TOOLS = [
    place_market_order,
    place_limit_order,
    place_stop_order,
    place_stop_limit_order,
    place_trailing_stop_order,
    place_bracket_market_order,
    replace_order,
    cancel_order,
    close_position,
]


ADMIN_TOOLS = [
    cancel_all_orders,
    close_all_positions,
]


ALL_ALPACA_TOOLS = (
    READ_ONLY_TOOLS
    + EXECUTION_TOOLS
    + ADMIN_TOOLS
)