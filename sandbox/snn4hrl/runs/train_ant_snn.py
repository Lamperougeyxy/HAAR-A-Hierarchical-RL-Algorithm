from rllab.baselines.linear_feature_baseline import LinearFeatureBaseline
from rllab.envs.normalized_env import normalize
from rllab.misc.instrument import stub, run_experiment_lite
from sandbox.snn4hrl.algos.trpo_snn import TRPO_snn
from sandbox.snn4hrl.bonus_evaluators.grid_bonus_evaluator import GridBonusEvaluator
from sandbox.snn4hrl.envs.mujoco.ant_env_backup import AntEnv
from sandbox.snn4hrl.policies.snn_mlp_policy import GaussianMLPPolicy_snn
from sandbox.snn4hrl.regressors.latent_regressor import Latent_regressor

stub(globals())

# SNN policy settings
latent_dim = 6   # dim of the latent variables in the SNN

# Bonus evaluator settings
mesh_density = 5  # for the discretization of the x-y space
snn_H_bonus = 1.0  # coef of the MI bonus

# extra arguments, not used in the paper
switch_lat_every = 0  # switch latents during the pre-training
virtual_reset = False
# Latent regressor (to avoid using the GridBonus evaluator and its discretization)
noisify_coef = 0        # noise injected int the state while fitting/predicting latents
reward_regressor_mi = 0         # bonus associated to the MI computed with the regressor

# choose your environment. For later hierarchization, choose ego_obs=True
env = normalize(AntEnv(ego_obs=True))

policy = GaussianMLPPolicy_snn(
    env_spec=env.spec,
    latent_dim=latent_dim,
    latent_name='categorical',
    bilinear_integration=True,  # concatenate also the outer product
    hidden_sizes=(64, 64),
    min_std=1e-6,
)

baseline = LinearFeatureBaseline(env_spec=env.spec)

if latent_dim:
    latent_regressor = Latent_regressor(
        env_spec=env.spec,
        policy=policy,
        predict_all=True,     # use all the predictions and not only the last
        obs_regressed='all',  # [-3] is the x-position of the com, otherwise put 'all'
        act_regressed=[],     # use [] for nothing or 'all' for all.
        noisify_traj_coef=noisify_coef,
        regressor_args={
            'hidden_sizes': (32, 32),
            'name': 'latent_reg',
            'use_trust_region': False,
        }
    )
else:
    latent_regressor = None

bonus_evaluators = [GridBonusEvaluator(mesh_density=mesh_density, snn_H_bonus=snn_H_bonus,
                                       virtual_reset=virtual_reset,
                                       switch_lat_every=switch_lat_every,
                                       )]
reward_coef_bonus = [1]

algo = TRPO_snn(
    env=env,
    policy=policy,
    baseline=baseline,
    self_normalize=True,
    log_individual_latents=True,
    log_deterministic=True,
    latent_regressor=latent_regressor,
    reward_regressor_mi=reward_regressor_mi,
    bonus_evaluator=bonus_evaluators,
    reward_coef_bonus=reward_coef_bonus,
    switch_lat_every=switch_lat_every,
    batch_size=50000,
    whole_paths=True,
    max_path_length=500,
    n_itr=1000,
    discount=0.99,
    step_size=0.01,
)

for s in range(10, 110, 10):  # [10, 20, 30, 40, 50]:
    exp_prefix = 'Ant-snn'
    exp_name = exp_prefix + '_{}MI_{}grid_{}latCat_bil_{:04d}'.format(
        ''.join(str(snn_H_bonus).split('.')), mesh_density,
        latent_dim, s)

    run_experiment_lite(
        stub_method_call=algo.train(),
        use_cloudpickle=False,
        mode='local',
        pre_commands=['pip install --upgrade pip',
                      'pip install --upgrade theano',
                      ],
        # Number of parallel workers for sampling
        n_parallel=16,
        # Only keep the snapshot parameters for the last iteration
        snapshot_mode="last",
        # Specifies the seed for the experiment. If this is not provided, a random seed
        # will be used
        seed=s,
        # plot=True,
        # Save to data/ec2/exp_prefix/exp_name/
        exp_prefix=exp_prefix,
        exp_name=exp_name,
        sync_s3_pkl=True,  # for sync the pkl file also during the training
        sync_s3_png=True,
        terminate_machine=True,  # dangerous to have False!
    )
