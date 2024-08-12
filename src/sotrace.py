
#!/bin/env python3
#
# sotrace.py
#
# shared object trace
#
# Usage:
#    sotrace.py /path/to/binary out.dot
#    dot -Tout.svg out.dot
#
# (c)2024 Bram Stolk


import os	# For popen
import sys	# For argv
import fire
import subprocess
import shlex
import loguru as log

# Given a target library name, see what this library directly depends on.
def dep_list(target) :
    obj_cmd = ["readelf",  "-d", target]
    grep_cmd = ["grep", "NEEDED"]
    try:
        lines = subprocess.check_output(
			shlex.join(obj_cmd) + "|" + shlex.join(grep_cmd),
			shell=True).decode('utf-8')
        vals = [ x.split()[-1].strip() for x in lines.split('\n') if len(x.split()) > 1]
        deps = [ x[1:-1] for x in vals ]
        return deps
    except subprocess.CalledProcessError as err:
        log.logger.error(err)
        
        
     


# Given a set of dependency names, check to what path the are resolved using ldd
def dep_to_lib(target, deps) :
    cmd = ["ldd", target]
    try:
        lines = subprocess.check_output(shlex.join(cmd), shell=True).decode("utf-8")
        mapping = {}
        for line in lines.split('\n'):
            if "=>" in line:
                parts = line.strip().split(" => ")
                nam = parts[0].strip()
                if nam in deps :
                    mapping[nam] = parts[1].split(" (")[0]
        return mapping
    except subprocess.CalledProcessError as err:
        log.logger.error(err)


# Walk the dependencies of the target, and write the graph to file.
def traverse_so(target, nam, f, depth, visited, linked, keep_suffix) :
    visited.add(target)
    deps = dep_list(target)
    lib_map = dep_to_lib(target, deps)
    if isinstance(lib_map, dict):
        for val in lib_map.keys() :
            link = (nam, val) if keep_suffix else (nam.split('.so')[0], val.split('.so')[0])
            linked.add(link)
            for dep in deps:
                if dep in lib_map:
                    m = lib_map[dep]
                    if m not in visited:
                        visited.add(m)
                        dnam = os.path.basename(dep)
                        traverse_so(m, dnam, f, depth+1, visited, linked, keep_suffix)


# Walk the deps, starting from the mapped files of a process.
def trace_pid(target, f, visited, linked, keep_suffix) :
    with open(f"/proc/{target}/comm", "r") as nf:
	    nam = nf.readline().strip()
    cmd = ['ls', "-l", f"/proc/{target}/map_files"]
    try:
        cf = subprocess.check_output(shlex.join(cmd), shell=True).decode('utf-8')
    except subprocess.CalledProcessError as err:
        log.logger.error(err)
        log.logger.info("Try sudo mode")
        sudo_cmd = ["sudo", 'ls', "-l", f"/proc/{target}/map_files"]
        cf = subprocess.check_output(shlex.join(sudo_cmd), shell=True).decode('utf-8')
    lines = [ x.split(" -> ")[1].strip() for x in cf.split('\n') if " -> " in x and ".so" in x ]
    libs = sorted(set(lines))
    print("Tracing shared objects from command", nam, "with", len(lines), "mapped .so files.")
    lib_map = {}

    depth = 0

    for lib in libs:
        libname = os.path.basename(lib)
        lib_map[libname] = lib

    for val in lib_map.keys() :
        if keep_suffix :
            link = (nam, val)
            linked.add(link)
        else :
            link = (nam.split('.so')[0], val.split('.so')[0])
            linked.add(link)

    for dep in lib_map.keys() :
        if dep in lib_map :
            m = lib_map[dep]
            if m not in visited :
                visited.add(m)
                dnam = os.path.basename(dep)
                traverse_so(m, dnam, f, depth+1, visited, linked, keep_suffix)


def sotrace(target: str, out: str):
    """Cli tools to create the dependecies graph 
    

    Args:
        target (str): binary file or Process ID
        out (str): graph file output with the .dot extention
    """
    if target is None or out is None:
        print(f"Usage:    {sys.argv[0]} libfoo.so out.dot")
        print(f"Alt Usage: {sys.argv[0]} <PID> out.dot")
    
    target = str(target)
    nam = os.path.basename(target)
    with open(out, "w") as f:
        f.write("digraph G {\n")
        f.write("  rankdir = LR;\n")

        linked = set()
        visited = set()

        if target.isnumeric() :
            keep_suffix = False
            trace_pid(target, f, visited, linked, keep_suffix)
        else:
            keep_suffix = True
            traverse_so(target, nam, f, 0, visited, linked, keep_suffix)

        for link in linked :
            f.write(f'"{link[0]}" -> "{link[1]}"\n')

        f.write("}\n")

def main():
    fire.Fire(sotrace)
	
     
# Main entry point
if __name__ == '__main__' :
    main()