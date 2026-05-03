%GENERATE_MATPOWER_FIXTURES Export MATPOWER cases and solved PF fixtures.
%
% Run from the repository root with:
%   octave --quiet scripts/generate_matpower_fixtures.m

repo_root = fileparts(fileparts(mfilename('fullpath')));
matpower_dir = fullfile(repo_root, '.external', 'matpower');
data_dir = fullfile(repo_root, 'data');

if exist(matpower_dir, 'dir') ~= 7
    error('MATPOWER directory not found: %s', matpower_dir);
end
if exist(data_dir, 'dir') ~= 7
    mkdir(data_dir);
end

addpath(genpath(matpower_dir));

mpopt = mpoption( ...
    'pf.alg', 'NR', ...
    'pf.enforce_q_lims', 0, ...
    'pf.tol', 1e-10, ...
    'verbose', 0, ...
    'out.all', 0 ...
);

matpower_version = mpver();
octave_version_value = version();
matpower_commit = git_commit(matpower_dir);
source_url = 'https://github.com/MATPOWER/matpower.git';

case_names = {'case9', 'case14', 'case30'};
for idx = 1:length(case_names)
    case_name = case_names{idx};
    mpc = feval(case_name);
    results = runpf(mpc, mpopt);
    if ~results.success
        error('MATPOWER runpf did not converge for %s', case_name);
    end

    case_payload = case_payload_from_mpc( ...
        mpc, case_name, matpower_version, matpower_commit, source_url);
    solution_payload = solution_payload_from_results( ...
        results, case_name, matpower_version, octave_version_value, matpower_commit, source_url);

    write_pretty_json(fullfile(data_dir, [case_name '.json']), case_payload);
    write_pretty_json(fullfile(data_dir, [case_name '_solution.json']), solution_payload);
end

export_optional_soln9(repo_root, data_dir, matpower_version, octave_version_value, matpower_commit, source_url);


function payload = case_payload_from_mpc(mpc, case_name, matpower_version, matpower_commit, source_url)
base_mva = mpc.baseMVA;
gen_by_bus = containers.Map('KeyType', 'double', 'ValueType', 'any');
for row = 1:size(mpc.gen, 1)
    if mpc.gen(row, 8) == 0
        continue;
    end
    bus_id = mpc.gen(row, 1);
    if isKey(gen_by_bus, bus_id)
        pq = gen_by_bus(bus_id);
    else
        pq = [0, 0];
    end
    pq(1) = pq(1) + mpc.gen(row, 2);
    pq(2) = pq(2) + mpc.gen(row, 3);
    gen_by_bus(bus_id) = pq;
end

buses = {};
for row = 1:size(mpc.bus, 1)
    bus_id = mpc.bus(row, 1);
    matpower_type = mpc.bus(row, 2);
    if matpower_type == 3
        bus_type = 'slack';
    elseif matpower_type == 2
        bus_type = 'pv';
    elseif matpower_type == 1
        bus_type = 'pq';
    else
        error('Unsupported MATPOWER bus type %.0f at bus %.0f', matpower_type, bus_id);
    end

    if isKey(gen_by_bus, bus_id)
        pq = gen_by_bus(bus_id);
    else
        pq = [0, 0];
    end

    buses{end + 1} = struct( ...
        'id', bus_id, ...
        'type', bus_type, ...
        'p_load', mpc.bus(row, 3) / base_mva, ...
        'q_load', mpc.bus(row, 4) / base_mva, ...
        'p_gen', pq(1) / base_mva, ...
        'q_gen', pq(2) / base_mva, ...
        'v_magnitude', mpc.bus(row, 8), ...
        'v_angle', deg2rad(mpc.bus(row, 9)), ...
        'g_shunt', mpc.bus(row, 5) / base_mva, ...
        'b_shunt', mpc.bus(row, 6) / base_mva ...
    );
end

branches = {};
for row = 1:size(mpc.branch, 1)
    ratio = mpc.branch(row, 9);
    if ratio == 0
        ratio = 1;
    end
    branches{end + 1} = struct( ...
        'from_bus', mpc.branch(row, 1), ...
        'to_bus', mpc.branch(row, 2), ...
        'r', mpc.branch(row, 3), ...
        'x', mpc.branch(row, 4), ...
        'b', mpc.branch(row, 5), ...
        'tap_ratio', ratio, ...
        'phase_shift', deg2rad(mpc.branch(row, 10)), ...
        'status', mpc.branch(row, 11) ...
    );
end

payload = struct( ...
    'metadata', metadata(case_name, matpower_version, '', matpower_commit, source_url), ...
    'base_mva', base_mva, ...
    'buses', {buses}, ...
    'branches', {branches} ...
);
end


function payload = solution_payload_from_results(results, case_name, matpower_version, octave_version_value, matpower_commit, source_url)
payload = solution_payload_from_matrices( ...
    results.baseMVA, results.bus, results.gen, results.branch, ...
    case_name, matpower_version, octave_version_value, matpower_commit, source_url);
end


function payload = solution_payload_from_matrices(base_mva, bus_matrix, gen_matrix, branch_matrix, case_name, matpower_version, octave_version_value, matpower_commit, source_url)
buses = {};
for row = 1:size(bus_matrix, 1)
    buses{end + 1} = struct( ...
        'id', bus_matrix(row, 1), ...
        'v_magnitude', bus_matrix(row, 8), ...
        'v_angle_degrees', bus_matrix(row, 9) ...
    );
end

generators = {};
for row = 1:size(gen_matrix, 1)
    generators{end + 1} = struct( ...
        'bus_id', gen_matrix(row, 1), ...
        'p_generation', gen_matrix(row, 2) / base_mva, ...
        'q_generation', gen_matrix(row, 3) / base_mva ...
    );
end

branches = {};
for row = 1:size(branch_matrix, 1)
    branches{end + 1} = struct( ...
        'from_bus', branch_matrix(row, 1), ...
        'to_bus', branch_matrix(row, 2), ...
        'p_from', branch_matrix(row, 14) / base_mva, ...
        'q_from', branch_matrix(row, 15) / base_mva, ...
        'p_to', branch_matrix(row, 16) / base_mva, ...
        'q_to', branch_matrix(row, 17) / base_mva ...
    );
end

md = metadata(case_name, matpower_version, octave_version_value, matpower_commit, source_url);
md.command = sprintf('runpf(''%s'', mpopt)', case_name);
md.base_mva = base_mva;
md.unit_conversions = 'MW/MVAr converted to p.u. on baseMVA; voltage angles kept in degrees in solution fixtures.';

payload = struct( ...
    'metadata', md, ...
    'buses', {buses}, ...
    'generators', {generators}, ...
    'branches', {branches} ...
);
end


function export_optional_soln9(repo_root, data_dir, matpower_version, octave_version_value, matpower_commit, source_url)
t_case = fullfile(repo_root, '.external', 'matpower', 'lib', 't', 't_case9_pf.m');
soln = fullfile(repo_root, '.external', 'matpower', 'lib', 't', 'soln9_pf.mat');
if exist(t_case, 'file') ~= 2 || exist(soln, 'file') ~= 2
    return;
end

mpc = t_case9_pf();
case_payload = case_payload_from_mpc(mpc, 't_case9_pf', matpower_version, matpower_commit, source_url);
write_pretty_json(fullfile(data_dir, 't_case9_pf.json'), case_payload);

loaded = load(soln);
solution_payload = solution_payload_from_matrices( ...
    mpc.baseMVA, loaded.bus_soln, loaded.gen_soln, loaded.branch_soln, ...
    'soln9_pf', matpower_version, octave_version_value, matpower_commit, source_url);
write_pretty_json(fullfile(data_dir, 'soln9_pf.json'), solution_payload);
end


function md = metadata(case_name, matpower_version, octave_version_value, matpower_commit, source_url)
md = struct( ...
    'source_case', case_name, ...
    'matpower_version', matpower_version, ...
    'matpower_commit', matpower_commit, ...
    'source_url', source_url, ...
    'generated_by', 'scripts/generate_matpower_fixtures.m' ...
);
if ~isempty(octave_version_value)
    md.octave_version = octave_version_value;
end
end


function commit = git_commit(path)
[status, output] = system(sprintf('git -C "%s" rev-parse HEAD', path));
if status == 0
    commit = strtrim(output);
else
    commit = '';
end
end


function write_pretty_json(path, payload)
compact = jsonencode(payload);
tmp_path = [path '.compact'];
fid = fopen(tmp_path, 'w');
if fid == -1
    error('Could not open %s for writing', tmp_path);
end
fprintf(fid, '%s\n', compact);
fclose(fid);

[status, ~] = system(sprintf('python3 -m json.tool --indent 2 "%s" "%s"', tmp_path, path));
delete(tmp_path);
if status == 0
    return;
else
    fid = fopen(path, 'w');
    if fid == -1
        error('Could not open %s for writing', path);
    end
    fprintf(fid, '%s\n', compact);
    fclose(fid);
end
end
