from pathlib import Path


source_path = Path("NootedGreen/kern_gen11.cpp")
source = source_path.read_text()


def require_count(token: str, expected: int, label: str) -> None:
    actual = source.count(token)
    if actual != expected:
        raise SystemExit(
            f"Stage18G safety: {label}: expected {expected}, found {actual}"
        )


def replace_once(old: str, new: str, label: str) -> None:
    global source
    actual = source.count(old)
    if actual != 1:
        raise SystemExit(
            f"Stage18G patch: {label}: expected one anchor, found {actual}"
        )
    source = source.replace(old, new, 1)


# The diagnostic must remain Stage18F plus one pass-through start route.  These
# guards ensure that no previously disabled broad framebuffer group is enabled.
require_count("const bool st18cEnableFBRoutes = false;", 1, "Stage18C guard")
require_count("if (st18cEnableFBRoutes) {", 3, "disabled broad route groups")
for marker in (
    "ST18D:PW00",
    "ST18D:PGE ENTER",
    "ST18D:AUX ENTER",
    "ST18D:DDI ENTER",
    "ST18F:PMODE-PROD-BEFORE",
    "ST18F:PMODE-DEBUG-BEFORE",
):
    require_count(marker, 1, marker)

for forbidden in (
    "ST18G:",
    "ST18G DEADMAN",
    "st18gFBStartProbe",
    "st18gSetPhase",
):
    require_count(forbidden, 0, f"pre-existing {forbidden}")

global_anchor = "Gen11 *Gen11::callback = nullptr;\n"
global_block = r'''

// Stage18G: diagnostic-only framebuffer start deadman.
//
// This wrapper is deliberately pass-through: it does not touch MMIO, change a
// return value, or enable any of the Stage18C broad framebuffer routes. It only
// records the latest Stage18D PowerWell phase and deliberately panics if
// AppleIntel{Base,Framebuffer}Controller::start() does not return in 30 seconds.
static mach_vm_address_t st18gOriginalFBStart = 0;
static volatile bool st18gFBStartActive = false;
static volatile uint32_t st18gPhase = 0;
static const char * volatile st18gPhaseName = "NOT_STARTED";

static void st18gSetPhase(uint32_t phase, const char *name) {
	st18gPhase = phase;
	st18gPhaseName = name;
}

static void st18gFBStartDeadman(thread_call_param_t, thread_call_param_t) {
	if (st18gFBStartActive) {
		panic("ST18G DEADMAN: FBController::start did not return within 30s; "
		      "last phase=%u (%s). This panic is deliberate diagnostic evidence.",
		      st18gPhase, st18gPhaseName ? st18gPhaseName : "<null>");
	}
	SYSLOG("ngreen", "ST18G:DEADMAN-DISARMED start returned before timeout");
}

static bool st18gFBStartProbe(void *that, IOService *provider) {
	st18gFBStartActive = true;
	st18gSetPhase(100, "FB_START_ENTER");

	auto deadman = thread_call_allocate(st18gFBStartDeadman, nullptr);
	if (!deadman)
		panic("ST18G DEADMAN: thread_call_allocate failed");

	uint64_t deadline = 0;
	clock_interval_to_deadline(30, kSecondScale, &deadline);
	thread_call_enter_delayed(deadman, deadline);
	SYSLOG("ngreen", "ST18G:DEADMAN-ARMED timeout=30s");

	const bool result = FunctionCast(st18gFBStartProbe, st18gOriginalFBStart)(that, provider);
	st18gSetPhase(199, "FB_START_RETURN");
	st18gFBStartActive = false;
	SYSLOG("ngreen", "ST18G:FBSTART-RETURN result=%d", result);
	return result;
}
'''
replace_once(
    global_anchor,
    global_anchor + global_block,
    "file-scope deadman block",
)

route_anchor = "\t\t// Stage18F: combine Stage18D's minimal ccont/PowerWell routes\n"
route_block = r'''
		// Stage18G: route only controller start to a diagnostic pass-through.
		// Stage18C broad framebuffer route groups remain disabled.
		if (isprod) {
			RouteRequestPlus st18gFBStartProdRequest[] = {
				{"__ZN31AppleIntelFramebufferController5startEP9IOService", st18gFBStartProbe, st18gOriginalFBStart},
			};
			SYSLOG("ngreen", "ST18G:FBSTART-ROUTE-PROD-BEFORE");
			PANIC_COND(!RouteRequestPlus::routeAll(patcher, index, st18gFBStartProdRequest, address, size),
				"ngreen", "Stage18G failed to route production FBController::start");
			SYSLOG("ngreen", "ST18G:FBSTART-ROUTE-PROD-AFTER");
		} else {
			RouteRequestPlus st18gFBStartDebugRequest[] = {
				{"__ZN24AppleIntelBaseController5startEP9IOService", st18gFBStartProbe, st18gOriginalFBStart},
			};
			SYSLOG("ngreen", "ST18G:FBSTART-ROUTE-DEBUG-BEFORE");
			PANIC_COND(!RouteRequestPlus::routeAll(patcher, index, st18gFBStartDebugRequest, address, size),
				"ngreen", "Stage18G failed to route debug FBController::start");
			SYSLOG("ngreen", "ST18G:FBSTART-ROUTE-DEBUG-AFTER");
		}

'''
replace_once(route_anchor, route_block + route_anchor, "start route block")

replace_once(
    "void Gen11::hwSetPowerWellStatePGE(AppleIntel::AppleIntelBaseController *that, bool param_1, uint param_2)\n{\n",
    "void Gen11::hwSetPowerWellStatePGE(AppleIntel::AppleIntelBaseController *that, bool param_1, uint param_2)\n{\n"
    "\tst18gSetPhase(220, \"PGE_ENTER\");\n",
    "PGE enter",
)
replace_once(
    "\t\tNGreen::callback->writeReg32(0x45400, newVal);\n\t\treturn;\n",
    "\t\tNGreen::callback->writeReg32(0x45400, newVal);\n"
    "\t\tst18gSetPhase(221, \"PGE_RETURN\");\n\t\treturn;\n",
    "PGE non-TGL return",
)
replace_once(
    "\tFunctionCast(hwSetPowerWellStatePGE, callback->ohwSetPowerWellStatePGE)(that, param_1, param_2);\n",
    "\tFunctionCast(hwSetPowerWellStatePGE, callback->ohwSetPowerWellStatePGE)(that, param_1, param_2);\n"
    "\tst18gSetPhase(221, \"PGE_RETURN\");\n",
    "PGE real-TGL return",
)

replace_once(
    "void Gen11::hwSetPowerWellStateAux(AppleIntel::AppleIntelBaseController *that, bool param_1, uint param_2)\n{\n",
    "void Gen11::hwSetPowerWellStateAux(AppleIntel::AppleIntelBaseController *that, bool param_1, uint param_2)\n{\n"
    "\tst18gSetPhase(230, \"AUX_ENTER\");\n",
    "AUX enter",
)
replace_once(
    "\tFunctionCast(hwSetPowerWellStateAux, callback->ohwSetPowerWellStateAux)(that,param_1,param_2);\n",
    "\tFunctionCast(hwSetPowerWellStateAux, callback->ohwSetPowerWellStateAux)(that,param_1,param_2);\n"
    "\tst18gSetPhase(231, \"AUX_RETURN\");\n",
    "AUX return",
)

replace_once(
    "void Gen11::hwSetPowerWellStateDDI(AppleIntel::AppleIntelBaseController *that, bool param_1, uint param_2)\n{\n",
    "void Gen11::hwSetPowerWellStateDDI(AppleIntel::AppleIntelBaseController *that, bool param_1, uint param_2)\n{\n"
    "\tst18gSetPhase(240, \"DDI_ENTER\");\n",
    "DDI enter",
)
replace_once(
    "\tFunctionCast(hwSetPowerWellStateDDI, callback->ohwSetPowerWellStateDDI)(that,param_1,param_2);\n",
    "\tFunctionCast(hwSetPowerWellStateDDI, callback->ohwSetPowerWellStateDDI)(that,param_1,param_2);\n"
    "\tst18gSetPhase(241, \"DDI_RETURN\");\n",
    "DDI return",
)

replace_once(
    "void Gen11::AppleIntelPowerWellinit(AppleIntel::AppleIntelPowerWell *that, AppleIntel::AppleIntelBaseController *param_1)\n{\n",
    "void Gen11::AppleIntelPowerWellinit(AppleIntel::AppleIntelPowerWell *that, AppleIntel::AppleIntelBaseController *param_1)\n{\n"
    "\tst18gSetPhase(210, \"PW_INIT_ENTER\");\n",
    "PowerWell init enter",
)
replace_once(
    "\tFunctionCast(AppleIntelPowerWellinit, callback->oAppleIntelPowerWellinit)(that, param_1);\n",
    "\tFunctionCast(AppleIntelPowerWellinit, callback->oAppleIntelPowerWellinit)(that, param_1);\n"
    "\tst18gSetPhase(211, \"PW_INIT_RETURN\");\n",
    "PowerWell init return",
)

# Final source invariants: the old three broad groups are still guarded and the
# only new route is the single prod/debug controller-start diagnostic choice.
required_after = {
    "ST18G:DEADMAN-ARMED": 1,
    "ST18G:DEADMAN-DISARMED": 1,
    "ST18G:FBSTART-RETURN": 1,
    "ST18G DEADMAN: FBController::start did not return within 30s": 1,
    "ST18G:FBSTART-ROUTE-PROD-BEFORE": 1,
    "ST18G:FBSTART-ROUTE-DEBUG-BEFORE": 1,
    "FB_START_ENTER": 1,
    "PW_INIT_ENTER": 1,
    "PW_INIT_RETURN": 1,
    "PGE_ENTER": 1,
    "PGE_RETURN": 2,
    "AUX_ENTER": 1,
    "AUX_RETURN": 1,
    "DDI_ENTER": 1,
    "DDI_RETURN": 1,
}
for token, expected in required_after.items():
    require_count(token, expected, token)

require_count("const bool st18cEnableFBRoutes = false;", 1, "final Stage18C guard")
require_count("if (st18cEnableFBRoutes) {", 3, "final broad route guards")
source_path.write_text(source)
