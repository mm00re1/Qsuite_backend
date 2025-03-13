.oauth.connectionLogs: ([]userOrApp: `$(); kdb_username: `$(); tokenType: `$(); valid: `boolean$(); error: (); scope: `$(); role: `$());

.z.pw:{[u;p]
    .mm.u:u; .mm.p:p;
    res: system"python verify_token.py ",p;
    token_dict: .j.k raze res;
    role: first token_dict[`claims][`roles];
    scope: token_dict[`claims][`scp];

    // this is of course hardcoded to work with the specific roles setup for this demo example and assumes ...
    // ... the scope for user access and the role for application access have the same entitlements
    success:$[("read_data" ~ scope) or ("read_access_kdb" ~ role); 1b; 0b];
    `.oauth.connectionLogs upsert (`$token_dict[`userOrApp]; u; `$token_dict[`tokenType]; token_dict[`valid]; token_dict[`error]; `$scope; `$role);
    success
 };

/// Config Information ///
.config.syms:`MSFT`META`NVDA`TSLA`AAPL;
.config.prices:.config.syms!370.62 349.28 481.11 247.14  194.83;
n:2; /number of rows per update
flag:1; /generate 10% of updates for trade and 90% for quote
getmovement:{[s] rand[0.0001]*.config.prices[s]}; /get a random price movement 
/generate trade price
getprice:{[s] .config.prices[s]+:rand[1 -1]*getmovement[s]; .config.prices[s]} ;
getbid:{[s] .config.prices[s]-getmovement[s]}; /generate bid price
getask:{[s] .config.prices[s]+getmovement[s]}; /generate ask price

quote:([]time:`timestamp$();sym:`symbol$();bid:`float$();ask:`float$();bsize:`int$();asize:`int$());
trade:([]time:`timestamp$();sym:`symbol$();price:`float$();size:`int$());


\t 100

/// TIMER FUNCTION ///
.z.ts:{
  s:n?.config.syms;
  $[0<flag mod 10;
    [data:flip cols[quote]!(n#.z.P;s;getbid'[s];getask'[s];n?1000;n?1000);
    .u.upd[`quote;data];
    `quote upsert data];
    [data:flip cols[trade]!(n#.z.P;s;getprice'[s];n?1000);
    .u.upd[`trade;data];
    `trade upsert data]];
  flag+:1; };


/// Snapshot Query Funcs ///
.gw.pullData:{[tbl;querySym]
    //.mm.t:tbl; .mm.s:sym;
    tbl:`$tbl;
    $[tbl = `trade;
        select time.time, price from tbl where sym = `$querySym, time > (.z.T - 00:10:00.000);
        select time.time,bid,ask from tbl where sym = `$querySym, time > (.z.T - 00:10:00.000)]
 };

.gw.getIndexes:{[tbl] exec distinct sym from `$tbl};


/// Subscriber Handling Functions ///
.u.subscribers:`quote`trade!(`int$();`int$());
.u.subscriberSyms:(.config.syms)!(5#enlist `int$());
.u.sub:{[tbl;syms]
    .mm.tbl:tbl; .mm.syms: syms; .mm.h: .z.w;
    if[10h = type[tbl]; tbl:`$tbl];         // convert string to sym
    if[10h = type[syms]; syms:`$syms];      // convert string to sym
    if[-11h = type syms; syms:enlist syms]; // if they sub with 1 symbol, ensure its a list

    if[any not syms in key .u.subscriberSyms;:(::)];
    if[not tbl in key .u.subscribers; :(::)];
    .u.subscribers[tbl],:.z.w;
    {[sym] .u.subscriberSyms[sym],:.z.w} each syms;
    .mm.res:0#get tbl;
    0N!.mm.res;
    0#get tbl
 };

.u.upd:{[tbl;data]
    tblSubs: .u.subscribers[tbl];
    .u.filterForPublish[;tbl;data] each tblSubs;
 };

.u.filterForPublish:{[sub;tbl;data]
    pubSyms: key[.u.subscriberSyms] where sub in/: value .u.subscriberSyms;
    if[count pubData:select from data where sym in pubSyms;
        $[tbl = `trade;
            pubData: select time.time, price from pubData;
            pubData: select time.time, bid,ask from pubData];
        neg[sub](`upd;tbl;pubData)];
 };

.u.unsub:{[h]
    clientHandle: $[h~ "direct unsub";.z.w; h];
    {[tbl;h] .u.subscribers[tbl]: .u.subscribers[tbl] except h}[;clientHandle] each `quote`trade;
    {[sym;h] .u.subscriberSyms[sym]: .u.subscriberSyms[sym] except h}[;clientHandle] each key .u.subscriberSyms;
    "unsubbed"
 };

.z.pc:{ .u.unsub[x]};


// load other important scripts
\l qsuiteSetup.q
