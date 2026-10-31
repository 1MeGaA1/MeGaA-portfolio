pragma Singleton
import QtQuick

// Demo content mirroring the web client (currency / friends) plus the shop / events filter chips.
// Games and apps come from the real per-PC catalog via vortex.games()/vortex.apps(); shop
// products and events are managed in the admin panel (vortex.shop() / vortex.events() /
// vortex.featured()).
QtObject {
    // shop products come from the server (see vortex.shop()); only the category chips stay here.
    readonly property var shopCats: [
        { key: "all", label: "ALL" }, { key: "drinks", label: "DRINKS" },
        { key: "snacks", label: "SNACKS" }, { key: "meals", label: "MEALS" }
    ]

    readonly property var currency: [
        { key: "valorant", name: "Valorant",          cur: "VP",          balance: 0,    a: "#ff4655", b: "#5a1217" },
        { key: "lol",      name: "League of Legends", cur: "RP",          balance: 650,  a: "#c89b3c", b: "#463714" },
        { key: "fortnite", name: "Fortnite",          cur: "V-BUCKS",     balance: 1200, a: "#a855f7", b: "#1e5dbd" },
        { key: "fifa",     name: "FIFA 26",           cur: "FIFA POINTS", balance: 0,    a: "#1a4d2e", b: "#0a2615" },
        { key: "apex",     name: "Apex Legends",      cur: "APEX COINS",  balance: 250,  a: "#ea2f2f", b: "#3a0a0a" },
        { key: "cod",      name: "Call of Duty",      cur: "CP",          balance: 0,    a: "#3b2a12", b: "#1a1a1a" }
    ]
    // generic packs applied to whichever currency game is selected
    readonly property var currencyPacks: [
        { amount: 500,  price: 5 },
        { amount: 1000, price: 10 },
        { amount: 2500, price: 22 },
        { amount: 5000, price: 40 },
        { amount: 12000, price: 90 }
    ]

    // events come from the server (see vortex.events()); chips match the server's `cats` values
    readonly property var eventCats: [
        { key: "all", label: "ALL" }, { key: "live", label: "LIVE" },
        { key: "upcoming", label: "UPCOMING" }, { key: "weekly", label: "WEEKLY" },
        { key: "weekend", label: "WEEKEND" }, { key: "tournament", label: "TOURNAMENTS" },
        { key: "offer", label: "OFFERS" }
    ]

    // matches the original web friends menu (grouped online / offline, coloured avatars, full status)
    readonly property var friends: [
        { name: "phoenix_99",   online: true,  status: "Playing Valorant",   av: "#ff3d9a", avText: "#ffffff" },
        { name: "ghost_rider",  online: true,  status: "In menu",            av: "#00e5ff", avText: "#05050c" },
        { name: "cyber_claw",   online: true,  status: "Streaming · Twitch", av: "#00ff88", avText: "#05050c" },
        { name: "neon_x",       online: true,  status: "Browsing shop",      av: "#ffb800", avText: "#05050c" },
        { name: "midnight_v",   online: false, status: "offline · 2h ago" },
        { name: "quick_silver", online: false, status: "offline · yesterday" },
        { name: "shadow_k",     online: false, status: "offline · 3d ago" },
        { name: "void_walker",  online: false, status: "offline · 1w ago" }
    ]
}
