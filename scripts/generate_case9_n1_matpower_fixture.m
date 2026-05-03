1;

%GENERATE_CASE9_N1_MATPOWER_FIXTURE Export MATPOWER N-1 line-outage solutions.
%
% Run from the repository root with:
%   octave --quiet scripts/generate_case9_n1_matpower_fixture.m


function tf = is_transmission_loop_branch(from_bus, to_bus)
pairs = [
    4, 5;
    5, 6;
    6, 7;
    7, 8;
    8, 9;
    9, 4
];
tf = any(pairs(:, 1) == from_bus & pairs(:, 2) == to_bus);
end


function id = contingency_id(from_bus, to_bus)
id = sprintf('%.0f-%.0f', from_bus, to_bus);
end


function payload = solution_payload_from_results(results, from_bus, to_bus, removed_branch_row)
base_mva = results.baseMVA;

buses = {};
for row = 1:size(results.bus, 1)
    buses{end + 1} = struct( ...
        'id', results.bus(row, 1), ...
        'v_magnitude', results.bus(row, 8), ...
        'v_angle_degrees', results.bus(row, 9) ...
    );
end

generators = {};
for row = 1:size(results.gen, 1)
    generators{end + 1} = struct( ...
        'bus_id', results.gen(row, 1), ...
        'p_generation', results.gen(row, 2) / base_mva, ...
        'q_generation', results.gen(row, 3) / base_mva ...
    );
end

branches = {};
for row = 1:size(results.branch, 1)
    branches{end + 1} = struct( ...
        'from_bus', results.branch(row, 1), ...
        'to_bus', results.branch(row, 2), ...
        'p_from', results.branch(row, 14) / base_mva, ...
        'q_from', results.branch(row, 15) / base_mva, ...
        'p_to', results.branch(row, 16) / base_mva, ...
        'q_to', results.branch(row, 17) / base_mva ...
    );
end

payload = struct( ...
    'contingency_id', contingency_id(from_bus, to_bus), ...
    'from_bus', from_bus, ...
    'to_bus', to_bus, ...
    'removed_branch_row_1_based', removed_branch_row, ...
    'group', 'transmission_loop', ...
    'status', 'solved', ...
    'buses', {buses}, ...
    'generators', {generators}, ...
    'branches', {branches} ...
);
end


function md = metadata(matpower_version, octave_version_value, matpower_commit, source_url)
md = struct( ...
    'source_case', 'case9', ...
    'matpower_version', matpower_version, ...
    'matpower_commit', matpower_commit, ...
    'source_url', source_url, ...
    'generated_by', 'scripts/generate_case9_n1_matpower_fixture.m', ...
    'octave_version', octave_version_value, ...
    'command', 'runpf(case9 with each transmission-loop branch removed, mpopt)', ...
    'unit_conversions', 'MW/MVAr converted to p.u. on baseMVA; voltage angles kept in degrees.' ...
);
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

mpc = case9();
contingencies = {};
for row = 1:size(mpc.branch, 1)
    from_bus = mpc.branch(row, 1);
    to_bus = mpc.branch(row, 2);
    if ~is_transmission_loop_branch(from_bus, to_bus)
        continue;
    end

    outaged = mpc;
    outaged.branch(row, :) = [];
    results = runpf(outaged, mpopt);
    if ~results.success
        error('MATPOWER runpf did not converge for outage %.0f-%.0f', from_bus, to_bus);
    end
    contingencies{end + 1} = solution_payload_from_results(results, from_bus, to_bus, row);
end

payload = struct( ...
    'metadata', metadata(matpower_version, octave_version_value, matpower_commit, source_url), ...
    'contingencies', {contingencies} ...
);
write_pretty_json(fullfile(data_dir, 'case9_n1_solutions.json'), payload);
