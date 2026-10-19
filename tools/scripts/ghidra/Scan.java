// Ghidra headless 批量脚本：先按结构偏移扫描引用点，再反编译目标函数。
// 为什么不用 REA broker：62MB IL2CPP 首次分析约 2 小时，broker 进程在分析结束时曾退出导致
// 结果丢失；headless 单进程跑完即落盘，且一次可批量处理多个函数。
// 用法（args[0]=偏移列表，args[1]=VA 列表，逗号分隔；args[2]=每个偏移的打印上限，默认 300）：
//   analyzeHeadless <proj> p -import GameAssembly.dll -scriptPath <dir> -postScript Scan.java \
//     "0x370,0x318,0x15c" "0x1806fc420,0x1804b980" -deleteProject
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.OperandType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.scalar.Scalar;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class Scan extends GhidraScript {

    private static long parseHex(String s) {
        return Long.parseUnsignedLong(s.trim().replace("0x", ""), 16);
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String offsetArg = args.length > 0 ? args[0] : "";
        String vaArg = args.length > 1 ? args[1] : "";
        int limit = args.length > 2 ? Integer.parseInt(args[2].trim()) : 300;

        Set<Long> offsets = new LinkedHashSet<>();
        for (String s : offsetArg.split(",")) {
            if (!s.trim().isEmpty()) {
                offsets.add(parseHex(s));
            }
        }
        List<Long> vas = new ArrayList<>();
        for (String s : vaArg.split(",")) {
            if (!s.trim().isEmpty()) {
                vas.add(parseHex(s));
            }
        }

        FunctionManager fm = currentProgram.getFunctionManager();
        Map<Long, List<String>> hits = new LinkedHashMap<>();
        Set<Long> foundFns = new LinkedHashSet<>();
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            for (int i = 0; i < ins.getNumOperands(); i++) {
                String repr = ins.getDefaultOperandRepresentation(i);
                if (repr == null || !repr.contains("[")) {
                    continue;   // 只看内存引用，排除立即数
                }
                for (Object o : ins.getOpObjects(i)) {
                    if (!(o instanceof Scalar)) {
                        continue;
                    }
                    long v = ((Scalar) o).getUnsignedValue();
                    if (!offsets.contains(v)) {
                        continue;
                    }
                    Function f = fm.getFunctionContaining(ins.getAddress());
                    long ep = f == null ? 0L : f.getEntryPoint().getOffset();
                    // W/R 前缀：区分「写这个字段」与「读这个字段」，消费方只可能是读
                    boolean wr = (ins.getOperandType(i) & OperandType.WRITE) != 0;
                    List<String> rows = hits.computeIfAbsent(v, k -> new ArrayList<>());
                    if (rows.size() < limit) {
                        rows.add((wr ? "W " : "R ") + (f == null ? "?" : f.getName())
                                 + " @" + ins.getAddress() + " : " + ins.toString());
                    }
                    if (f != null) {
                        foundFns.add(ep);
                    }
                }
            }
        }
        for (Map.Entry<Long, List<String>> e : hits.entrySet()) {
            println("##### offset 0x" + Long.toHexString(e.getKey())
                    + " hits=" + e.getValue().size() + " (limit " + limit + ")");
            for (String s : e.getValue()) {
                println("  " + s);
            }
        }
        if (foundFns.size() > 60) {
            println("##### 命中函数过多（" + foundFns.size() + "），只反编译前 60 个");
        }

        Set<Long> targets = new LinkedHashSet<>(vas);
        int n = 0;
        for (Long ep : foundFns) {
            if (n++ >= 60) {
                break;
            }
            targets.add(ep);
        }
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        for (Long va : targets) {
            Address addr = toAddr(va.longValue());
            Function f = fm.getFunctionAt(addr);
            if (f == null) {
                f = fm.getFunctionContaining(addr);
            }
            println("\n===== VA 0x" + Long.toHexString(va)
                    + " fn=" + (f == null ? "null" : f.getName()));
            if (f == null) {
                continue;
            }
            DecompileResults r = di.decompileFunction(f, 180, monitor);
            if (r != null && r.decompileCompleted()) {
                println(r.getDecompiledFunction().getC());
            } else {
                println("decompile failed");
            }
        }
        di.dispose();
    }
}
